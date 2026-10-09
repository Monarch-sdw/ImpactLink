import os, secrets
from datetime import datetime, timedelta, timezone
from typing import Literal
import jwt
from pwdlib import PasswordHash
from fastapi import FastAPI, Depends, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, text, func
from sqlalchemy.exc import IntegrityError
from .db import get_db
from .models import Organization, User, Project, Requirement, Offer, Partnership, Commitment, ProjectUpdate, Verification, Recommendation, now
from .schemas import Register, Login, OrgIn, OrgOut, ProjectIn, ProjectPatch, OfferIn, OfferOut, RequestIn, DeliveryIn, VerifyIn
from .matching import committed, delivered, rank, plan
from .schemas import UserOut, ProjectOut, RequirementOut, PartnershipOut, MatchOut, PlanRow

app = FastAPI(title='ImpactLink API', version='1.0.0', description='Resource coordination prototype. Demo data is fictional. Funding records are pledges, not payments.')
origins = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=['GET','POST','PATCH','PUT','DELETE'], allow_headers=['Content-Type','Authorization'])
SECRET = os.getenv('JWT_SECRET') or secrets.token_urlsafe(48)
DEMO = os.getenv('DEMO_MODE', 'false').lower() == 'true'
passwords = PasswordHash.recommended()

@app.middleware('http')
async def same_origin(request: Request, call_next):
    origin = request.headers.get('origin')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and origin not in origins:
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail': 'Untrusted request origin.'}, status_code=403)
    return await call_next(request)

def fail(status, message): raise HTTPException(status, message)

def record(db, cls, id):
    item = db.get(cls, id)
    if item is None: fail(404, 'Record not found.')
    return item

def current(request: Request, db=Depends(get_db)):
    token = request.cookies.get('impactlink_session')
    try:
        payload = jwt.decode(token or '', SECRET, algorithms=['HS256'])
        user = db.get(User, int(payload['sub']))
        if not user: fail(401, 'Please sign in.')
        return user
    except (jwt.PyJWTError, ValueError, KeyError): fail(401, 'Please sign in again.')

def owner(user, organization_id, role=None):
    if user.organization_id != organization_id or (role and user.role != role): fail(403, 'This action belongs to another organization or role.')

def admin(user):
    if user.role != 'admin': fail(403, 'Administrator access required.')

def user_info(db, user):
    return {'id': user.id, 'name': user.name, 'email': user.email, 'role': user.role, 'organization': OrgOut.model_validate(db.get(Organization, user.organization_id)).model_dump()}

def login_response(db, user, response):
    token = jwt.encode({'sub': str(user.id), 'exp': datetime.now(timezone.utc) + timedelta(hours=8)}, SECRET, algorithm='HS256')
    response.set_cookie('impactlink_session', token, httponly=True, samesite='lax', secure=os.getenv('COOKIE_SECURE','false') == 'true', max_age=28800, path='/')
    return user_info(db, user)

def write_lock(db):
    # Each mutation starts with a fresh transaction. SQLite serializes writers;
    # PostgreSQL uses a transaction-scoped advisory lock across ALL capacity edits.
    db.rollback()
    if db.bind.dialect.name == 'sqlite': db.execute(text('BEGIN IMMEDIATE'))
    else: db.execute(text('SELECT pg_advisory_xact_lock(170036)'))

@app.get('/health')
def health(): return {'status': 'ok', 'demo_mode': DEMO, 'ai_enabled': False}

@app.post('/auth/register', status_code=201, response_model=UserOut)
def register(data: Register, response: Response, db=Depends(get_db)):
    if (data.role == 'ngo') != (data.organization.organization_type == 'ngo'): fail(422, 'Organization type must match the account role.')
    org = Organization(**data.organization.model_dump())
    db.add(org); db.flush()
    user = User(name=data.name, email=data.email.lower(), password_hash=passwords.hash(data.password), role=data.role, organization_id=org.id)
    db.add(user)
    try: db.commit()
    except IntegrityError:
        db.rollback(); fail(409, 'Email is already registered.')
    return login_response(db, user, response)

@app.post('/auth/login', response_model=UserOut)
def login(data: Login, response: Response, db=Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not passwords.verify(data.password, user.password_hash): fail(401, 'Email or password is incorrect.')
    return login_response(db, user, response)

@app.get('/auth/demo-accounts')
def demo_accounts(db=Depends(get_db)):
    if not DEMO: return []
    return [{'id': u.id, 'name': u.name, 'role': u.role, 'organization_name': db.get(Organization,u.organization_id).name} for u in db.scalars(select(User).join(Organization).where(Organization.is_demo == True).order_by(User.id))]

@app.post('/auth/demo/{user_id}')
def demo_login(user_id: int, response: Response, db=Depends(get_db)):
    if not DEMO: fail(404, 'Demo mode is disabled.')
    user = record(db, User, user_id)
    if not db.get(Organization,user.organization_id).is_demo: fail(403, 'Not a demonstration account.')
    return login_response(db, user, response)

@app.get('/auth/me', response_model=UserOut)
def me(user=Depends(current), db=Depends(get_db)): return user_info(db,user)

@app.post('/auth/logout')
def logout(response: Response):
    response.delete_cookie('impactlink_session', path='/'); return {'message': 'Signed out.'}

@app.get('/organizations', response_model=list[OrgOut])
def organizations(db=Depends(get_db)): return list(db.scalars(select(Organization).order_by(Organization.id)))

@app.get('/organizations/{id}', response_model=OrgOut)
def organization(id:int, db=Depends(get_db)): return record(db,Organization,id)

@app.put('/organizations/{id}', response_model=OrgOut)
def update_org(id:int, data:OrgIn, user=Depends(current), db=Depends(get_db)):
    owner(user,id); write_lock(db)
    org=record(db,Organization,id)
    if data.organization_type != org.organization_type: fail(409,'Organization type cannot be changed.')
    for key,value in data.model_dump().items(): setattr(org,key,value)
    if org.verification_status != 'rejected': org.verification_status='pending'
    db.commit(); return org

def project_data(db,p):
    reqs=[]
    for r in db.scalars(select(Requirement).where(Requirement.project_id==p.id).order_by(Requirement.id)):
        c,d=committed(db,requirement_id=r.id),delivered(db,r.id)
        reqs.append({**jsonable_encoder(r), 'committed':c,'delivered':d,'remaining':max(0,r.quantity-c)})
    progress = round(sum(min(1,r['committed']/r['quantity']) for r in reqs)/len(reqs)*100) if reqs else 0
    return {**jsonable_encoder(p), 'organization_name':db.get(Organization,p.organizer_id).name,'requirements':reqs,'progress':progress}

@app.get('/projects', response_model=list[ProjectOut])
def projects(search:str='', sdg:int|None=None, resource_type:str='', location:str='', urgency:str='', status:str='', mine:bool=False, request:Request=None, db=Depends(get_db)):
    q=select(Project).order_by(Project.id)
    if search: q=q.where(Project.title.ilike(f'%{search}%'))
    if sdg: q=q.where(Project.sdg==sdg)
    if location: q=q.where(Project.location.ilike(f'%{location}%'))
    if urgency: q=q.where(Project.urgency==urgency)
    if status: q=q.where(Project.status==status)
    if resource_type: q=q.where(Project.id.in_(select(Requirement.project_id).where(Requirement.resource_type==resource_type)))
    if mine: q=q.where(Project.organizer_id==current(request,db).organization_id)
    return [project_data(db,p) for p in db.scalars(q)]

@app.post('/projects', status_code=201, response_model=ProjectOut)
def create_project(data:ProjectIn,user=Depends(current),db=Depends(get_db)):
    if user.role!='ngo': fail(403,'Only NGO accounts can create projects.')
    if db.get(Organization,user.organization_id).verification_status=='rejected': fail(403,'Organization is suspended.')
    p=Project(**data.model_dump(exclude={'requirements'}),organizer_id=user.organization_id,is_demo=db.get(Organization,user.organization_id).is_demo)
    db.add(p); db.flush()
    for r in data.requirements: db.add(Requirement(project_id=p.id,**r.model_dump()))
    db.commit(); return project_data(db,p)

@app.get('/projects/{id}', response_model=ProjectOut)
def project(id:int,db=Depends(get_db)): return project_data(db,record(db,Project,id))

@app.get('/projects/{id}/requirements', response_model=list[RequirementOut])
def requirements(id:int,db=Depends(get_db)): return project_data(db,record(db,Project,id))['requirements']

@app.patch('/projects/{id}')
def edit_project(id:int,data:ProjectPatch,user=Depends(current),db=Depends(get_db)):
    write_lock(db); p=record(db,Project,id); owner(user,p.organizer_id,'ngo')
    if data.status=='completed':
        for r in db.scalars(select(Requirement).where(Requirement.project_id==id)):
            if delivered(db,r.id)<r.quantity: fail(409,'Record all required deliveries before completing this project.')
    if data.verified_beneficiaries is not None or data.outcome_evidence is not None:
        fail(403, 'Only administrators can change verified outcomes or their evidence through the outcome review endpoint.')
    for key,value in data.model_dump(exclude_none=True,exclude={'update'}).items(): setattr(p,key,value)
    if data.status=='cancelled':
        for req in db.scalars(select(Partnership).where(Partnership.project_id==id)):
            if req.status=='pending': req.status='cancelled'
            if req.status=='accepted':
                c=db.scalar(select(Commitment).where(Commitment.partnership_id==req.id))
                if c.delivered_quantity==0: db.delete(c); req.status='cancelled'
                else: c.confirmed_quantity=c.delivered_quantity; c.status='delivered'
    if data.update: db.add(ProjectUpdate(project_id=id,description=data.update))
    db.commit(); return project_data(db,p)

@app.get('/projects/{id}/updates')
def updates(id:int,db=Depends(get_db)):
    record(db,Project,id)
    return list(db.scalars(select(ProjectUpdate).where(ProjectUpdate.project_id==id).order_by(ProjectUpdate.id.desc())))

def offer_data(db,o):
    return {**jsonable_encoder(o),'available_capacity':max(0,o.total_capacity-committed(db,offer_id=o.id)),'organization_name':db.get(Organization,o.organization_id).name}

@app.get('/offers',response_model=list[OfferOut])
def offers(mine:bool=False,resource_type:str='',request:Request=None,db=Depends(get_db)):
    q=select(Offer).order_by(Offer.id)
    if mine: q=q.where(Offer.organization_id==current(request,db).organization_id)
    if resource_type: q=q.where(Offer.resource_type==resource_type)
    return [offer_data(db,o) for o in db.scalars(q)]

@app.post('/offers',status_code=201,response_model=OfferOut)
def create_offer(data:OfferIn,user=Depends(current),db=Depends(get_db)):
    if user.role!='contributor': fail(403,'A contributor account is required.')
    o=Offer(**data.model_dump(),organization_id=user.organization_id); db.add(o); db.commit(); return offer_data(db,o)

@app.put('/offers/{id}',response_model=OfferOut)
def edit_offer(id:int,data:OfferIn,user=Depends(current),db=Depends(get_db)):
    write_lock(db); o=record(db,Offer,id); owner(user,o.organization_id,'contributor')
    used=committed(db,offer_id=id)
    if data.total_capacity<used: fail(409,'Capacity cannot be below confirmed commitments.')
    if used and any(getattr(o,k)!=v for k,v in data.model_dump().items() if k not in ('total_capacity','status','conditions')): fail(409,'Committed offer specifications cannot change. Create another offer.')
    for k,v in data.model_dump().items(): setattr(o,k,v)
    db.commit(); return offer_data(db,o)

@app.delete('/offers/{id}')
def deactivate(id:int,user=Depends(current),db=Depends(get_db)):
    write_lock(db); o=record(db,Offer,id); owner(user,o.organization_id,'contributor'); o.status='inactive'; db.commit(); return {'message':'Offer deactivated; existing commitments are preserved.'}

@app.get('/requirements/{id}/matches', response_model=list[MatchOut])
def matches(id:int,db=Depends(get_db)):
    r=record(db,Requirement,id); return rank(db,db.get(Project,r.project_id),r)

@app.get('/projects/{id}/plan', response_model=list[PlanRow])
def preview_plan(id:int,db=Depends(get_db)): return plan(db,record(db,Project,id))

@app.post('/projects/{id}/plan', response_model=list[PlanRow])
def generate_plan(id:int,user=Depends(current),db=Depends(get_db)):
    p=record(db,Project,id); owner(user,p.organizer_id,'ngo'); result=plan(db,p)
    for row in result:
        for m in row['allocations']:
            old=db.scalar(select(Recommendation).where(Recommendation.requirement_id==row['requirement_id'],Recommendation.offer_id==m['offer_id']))
            if old: old.score=m['score']
            else: db.add(Recommendation(requirement_id=row['requirement_id'],offer_id=m['offer_id'],score=m['score']))
    try: db.commit()
    except IntegrityError: db.rollback()
    return result

def partnership_data(db,p):
    offer=db.get(Offer,p.offer_id); req=db.get(Requirement,p.requirement_id); project=db.get(Project,p.project_id)
    c=db.scalar(select(Commitment).where(Commitment.partnership_id==p.id))
    return {**jsonable_encoder(p),'project_title':project.title,'organizer_id':project.organizer_id,'organization_id':offer.organization_id,'organization_name':db.get(Organization,offer.organization_id).name,'resource_type':req.resource_type,'unit':req.unit,'commitment':jsonable_encoder(c) if c else None}

@app.get('/partnerships', response_model=list[PartnershipOut])
def partnerships(project_id:int|None=None,user=Depends(current),db=Depends(get_db)):
    q=select(Partnership).order_by(Partnership.id.desc())
    if project_id: q=q.where(Partnership.project_id==project_id)
    rows=[partnership_data(db,p) for p in db.scalars(q)]
    return [p for p in rows if user.role=='admin' or user.organization_id in (p['organizer_id'],p['organization_id'])]

@app.post('/partnerships',status_code=201)
def request_partnership(data:RequestIn,user=Depends(current),db=Depends(get_db)):
    write_lock(db); r=record(db,Requirement,data.requirement_id); p=record(db,Project,r.project_id); owner(user,p.organizer_id,'ngo')
    match=next((m for m in rank(db,p,r) if m['offer_id']==data.offer_id),None)
    if not match: fail(409,'Offer is no longer eligible. Refresh matching results.')
    if data.quantity>min(match['capacity'],r.quantity-committed(db,requirement_id=r.id)): fail(409,'Requested quantity exceeds available capacity or remaining need.')
    existing=db.scalar(select(Partnership).where(Partnership.requirement_id==r.id,Partnership.offer_id==data.offer_id))
    if existing: fail(409,'A request already exists for this offer and requirement.')
    req=Partnership(project_id=p.id,requirement_id=r.id,offer_id=data.offer_id,requested_quantity=data.quantity)
    db.add(req); db.commit(); return partnership_data(db,req)

@app.post('/partnerships/{id}/{action}')
def respond(id:int,action:Literal['accept','reject'],user=Depends(current),db=Depends(get_db)):
    write_lock(db); req=record(db,Partnership,id); offer=record(db,Offer,req.offer_id); owner(user,offer.organization_id,'contributor')
    if req.status!='pending': fail(409,'This request has already been handled.')
    if action=='accept':
        r=record(db,Requirement,req.requirement_id); p=record(db,Project,req.project_id)
        m=next((m for m in rank(db,p,r) if m['offer_id']==offer.id),None)
        if not m or req.requested_quantity>min(m['capacity'],r.quantity-committed(db,requirement_id=r.id)): fail(409,'Capacity or eligibility changed. Decline this request and coordinate a new offer.')
        db.add(Commitment(partnership_id=req.id,confirmed_quantity=req.requested_quantity,delivered_quantity=0))
        req.status='accepted'
    else: req.status='rejected'
    req.responded_at=now(); db.commit(); return partnership_data(db,req)

@app.put('/commitments/{id}/delivery')
def delivery(id:int,data:DeliveryIn,user=Depends(current),db=Depends(get_db)):
    write_lock(db); c=record(db,Commitment,id); req=record(db,Partnership,c.partnership_id); offer=record(db,Offer,req.offer_id); owner(user,offer.organization_id,'contributor')
    if data.delivered_quantity<c.delivered_quantity or data.delivered_quantity>c.confirmed_quantity: fail(409,'Delivered total must increase and cannot exceed the commitment.')
    c.delivered_quantity=data.delivered_quantity; c.status='delivered' if c.delivered_quantity==c.confirmed_quantity else 'partial'
    db.add(ProjectUpdate(project_id=req.project_id,update_type='delivery',description=f'{offer.resource_type}: cumulative delivery recorded as {c.delivered_quantity:g} {offer.unit}.'))
    db.commit(); return partnership_data(db,req)

@app.get('/dashboard')
def dashboard(mine:bool=False,request:Request=None,db=Depends(get_db)):
    user=current(request,db) if mine else None
    ps=list(db.scalars(select(Project)))
    if user and user.role=='ngo': ps=[p for p in ps if p.organizer_id==user.organization_id]
    links=[partnership_data(db,p) for p in db.scalars(select(Partnership))]
    if user: links=[p for p in links if user.organization_id in (p['organizer_id'],p['organization_id'])]
    def total(resource,key): return sum(p['commitment'][key] for p in links if p['resource_type']==resource and p['commitment'])
    reqs=[r for p in ps if p.status=='active' for r in project_data(db,p)['requirements']]
    unmet={}
    for r in reqs:
        key=f"{r['resource_type']} ({r['unit']})"
        unmet[key]=unmet.get(key,0)+r['remaining']
    sdgs={}
    for p in ps: sdgs[f'SDG {p.sdg}']=sdgs.get(f'SDG {p.sdg}',0)+1
    recommendations=db.scalar(select(func.count()).select_from(Recommendation))
    return {'organizations':db.scalar(select(func.count()).select_from(Organization)),'active_projects':sum(p.status=='active' for p in ps),'completed_projects':sum(p.status=='completed' for p in ps),'suggested_partnerships':recommendations,'accepted_partnerships':sum(p['status']=='accepted' for p in links),'pending_requests':sum(p['status']=='pending' for p in links),'funding_committed':total('Funding','confirmed_quantity'),'funding_delivered':total('Funding','delivered_quantity'),'volunteers_committed':total('Volunteers','confirmed_quantity'),'volunteers_deployed':total('Volunteers','delivered_quantity'),'verified_beneficiaries':sum(p.verified_beneficiaries for p in ps),'unmet': [{'name':k,'quantity':v} for k,v in unmet.items()],'sdgs':[{'name':k,'projects':v} for k,v in sdgs.items()],'demo_mode':DEMO,'contains_demo_data':any(p.is_demo for p in ps)}

@app.get('/admin/verifications',response_model=list[OrgOut])
def verifications(user=Depends(current),db=Depends(get_db)):
    admin(user); return list(db.scalars(select(Organization).order_by(Organization.id)))

@app.post('/admin/organizations/{id}/verification',response_model=OrgOut)
def verify(id:int,data:VerifyIn,user=Depends(current),db=Depends(get_db)):
    admin(user); write_lock(db); org=record(db,Organization,id); org.verification_status=data.status
    db.add(Verification(organization_id=id,reviewer_id=user.id,status=data.status)); db.commit(); return org

@app.post('/admin/projects/{id}/outcome')
def outcome(id:int,data:ProjectPatch,user=Depends(current),db=Depends(get_db)):
    admin(user)
    if data.verified_beneficiaries is None or not data.outcome_evidence: fail(422,'Beneficiary count and evidence are required.')
    p=record(db,Project,id); p.verified_beneficiaries=data.verified_beneficiaries; p.outcome_evidence=data.outcome_evidence
    db.commit(); return project_data(db,p)
