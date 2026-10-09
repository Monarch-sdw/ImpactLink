import os
os.environ['DEMO_MODE']='true'
from datetime import date,timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.db import Base,get_db
from app.main import app
from app.models import Organization,User,Project,Requirement,Offer
from app.matching import rank,plan

@pytest.fixture
def setup(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'test.db'),connect_args={'check_same_thread':False,'timeout':30})
    Base.metadata.create_all(engine); Session=sessionmaker(bind=engine,expire_on_commit=False)
    def db_override():
        with Session() as db: yield db
    app.dependency_overrides[get_db]=db_override
    with Session() as db:
        for i,role in enumerate(['ngo','contributor','contributor','ngo','admin'],1):
            org=Organization(id=i,name=f'Demo org {i}',organization_type='ngo' if role=='ngo' else 'company',location='Hyderabad',latitude=17.385,longitude=78.486,supported_sdgs=[4],verification_status='verified',is_demo=True)
            db.add(org);db.flush();db.add(User(id=i,name=role,email=f'user{i}@example.com',password_hash='unused',role=role,organization_id=i))
        db.commit()
    def client(id=1):
        c=TestClient(app);assert c.post(f'/auth/demo/{id}').status_code==200;return c
    yield client,Session
    app.dependency_overrides.clear();engine.dispose()

def project_payload(quantity=20,kind='Volunteers',unit='people',spec=None):
    start=str(date.today()+timedelta(days=5));end=str(date.today()+timedelta(days=30))
    return dict(title='A meaningful project',description='A community education programme with measured resource needs.',location='Hyderabad',latitude=17.385,longitude=78.486,sdg=4,urgency='High',start_date=start,end_date=end,expected_beneficiaries=100,requirements=[dict(resource_type=kind,quantity=quantity,unit=unit,specifications=spec or [],required_start=start,required_end=end)])

def offer_payload(quantity=15,kind='Volunteers',unit='people',spec=None):
    return dict(resource_type=kind,total_capacity=quantity,unit=unit,specifications=spec or [],available_start=str(date.today()),available_end=str(date.today()+timedelta(days=60)),location='Hyderabad',latitude=17.385,longitude=78.486,service_radius=50,remote=False)

def test_vercel_api_prefix_is_normalized():
    client=TestClient(app)
    response=client.get('/api/health')
    assert response.status_code==200
    assert response.json()['status']=='ok'
    assert "url: './openapi.json'" in client.get('/api/docs').text
    assert client.get('/api/openapi.json').status_code==200

def make(client,quantity=20,offer_qty=15):
    ngo=client(1);con=client(2)
    p=ngo.post('/projects',json=project_payload(quantity)).json();o=con.post('/offers',json=offer_payload(offer_qty)).json()
    return ngo,con,p,o

def test_creation_matching_partial_and_multi_partner(setup):
    client,_=setup;ngo,con,p,o=make(client)
    assert p['requirements'][0]['quantity']==20
    assert o['available_capacity']==15
    matches=ngo.get(f"/requirements/{p['requirements'][0]['id']}/matches").json()
    assert matches[0]['score']==95 # capacity 15/20, all other components one
    first=ngo.post(f"/projects/{p['id']}/plan").json()[0]
    assert first['shortage']==5 and first['allocations'][0]['quantity']==15
    assert con.get('/offers?mine=true').json()[0]['available_capacity']==15
    other=client(3).post('/offers',json=offer_payload(10)).json()
    full=ngo.post(f"/projects/{p['id']}/plan").json()[0]
    assert full['shortage']==0
    assert sum(a['quantity'] for a in full['allocations'])==20
    assert [a['quantity'] for a in full['allocations']]==[15,5]

def test_accept_delivery_and_dashboard(setup):
    client,_=setup;ngo,con,p,o=make(client,20,20)
    req=ngo.post('/partnerships',json={'requirement_id':p['requirements'][0]['id'],'offer_id':o['id'],'quantity':20})
    assert req.status_code==201
    assert ngo.get('/dashboard').json()['volunteers_committed']==0
    accepted=con.post(f"/partnerships/{req.json()['id']}/accept")
    assert accepted.status_code==200
    assert con.get('/offers?mine=true').json()[0]['available_capacity']==0
    assert ngo.get('/dashboard').json()['volunteers_committed']==20
    assert ngo.get('/dashboard').json()['volunteers_deployed']==0
    cid=accepted.json()['commitment']['id']
    assert con.put(f'/commitments/{cid}/delivery',json={'delivered_quantity':21}).status_code==409
    assert con.put(f'/commitments/{cid}/delivery',json={'delivered_quantity':7}).status_code==200
    assert con.put(f'/commitments/{cid}/delivery',json={'delivered_quantity':6}).status_code==409
    assert ngo.get('/dashboard').json()['volunteers_deployed']==7
    assert ngo.get('/dashboard').json()['verified_beneficiaries']==0
    assert ngo.patch(f"/projects/{p['id']}",json={'status':'completed'}).status_code==409
    assert con.put(f'/commitments/{cid}/delivery',json={'delivered_quantity':20}).status_code==200
    assert ngo.patch(f"/projects/{p['id']}",json={'status':'completed'}).status_code==200

def test_capacity_not_double_booked_concurrent(setup):
    client,_=setup;ngo,con,p,o=make(client,20,20)
    p2=ngo.post('/projects',json=project_payload()).json()
    requests=[]
    for project in [p,p2]: requests.append(ngo.post('/partnerships',json={'requirement_id':project['requirements'][0]['id'],'offer_id':o['id'],'quantity':20}).json()['id'])
    c1,c2=client(2),client(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(c.post,f'/partnerships/{rid}/accept') for c,rid in zip([c1,c2],requests)]
        statuses=sorted(f.result().status_code for f in futures)
    assert statuses==[200,409]
    assert con.get('/offers?mine=true').json()[0]['available_capacity']==0

def test_permissions_duplicates_and_validation(setup):
    client,_=setup;ngo,con,p,o=make(client)
    assert con.post('/projects',json=project_payload()).status_code==403
    assert ngo.post('/offers',json=offer_payload()).status_code==403
    assert client(4).patch(f"/projects/{p['id']}",json={'title':'Stolen title'}).status_code==403
    assert client(3).put(f"/offers/{o['id']}",json=offer_payload()).status_code==403
    assert ngo.post('/projects',json=project_payload(-1)).status_code==422
    assert con.post('/offers',json=offer_payload(0)).status_code==422
    assert con.post('/offers',json=offer_payload(500,'Funding','USD')).status_code==422
    data={'requirement_id':p['requirements'][0]['id'],'offer_id':o['id'],'quantity':10}
    req=ngo.post('/partnerships',json=data).json()
    assert ngo.post('/partnerships',json=data).status_code==409
    assert ngo.post(f"/partnerships/{req['id']}/accept").status_code==403
    assert client(3).post(f"/partnerships/{req['id']}/accept").status_code==403
    assert con.post(f"/partnerships/{req['id']}/reject").status_code==200
    assert con.post(f"/partnerships/{req['id']}/accept").status_code==409
    assert ngo.get('/admin/verifications').status_code==403
    assert ngo.patch(f"/projects/{p['id']}",json={'outcome_evidence':'Unreviewed evidence'}).status_code==403

@pytest.mark.parametrize('change',[{'unit':'boxes'},{'specifications':['different']},{'available_end':str(date.today()+timedelta(days=10))},{'status':'inactive'},{'latitude':None,'longitude':None},{'latitude':28.61,'longitude':77.21,'service_radius':1}])
def test_hard_filters(setup,change):
    client,_=setup;ngo,con=client(1),client(2)
    p=ngo.post('/projects',json=project_payload(10,'Equipment','laptops',['laptop'])).json()
    payload=offer_payload(10,'Equipment','laptops',['laptop']);payload.update(change)
    assert con.post('/offers',json=payload).status_code==201
    result=ngo.get(f"/projects/{p['id']}/plan").json()[0]
    assert result['shortage']==10 and result['allocations']==[]

def test_empty_and_ai_disabled(setup):
    client,_=setup;ngo=client(1)
    assert ngo.get('/health').json()['ai_enabled'] is False
    assert ngo.get('/dashboard').json()['active_projects']==0
    p=ngo.post('/projects',json=project_payload()).json()
    assert ngo.get(f"/projects/{p['id']}/plan").json()[0]['shortage']==20

def test_cross_requirement_capacity_and_cancel(setup):
    client,_=setup;ngo,con=client(1),client(2)
    data=project_payload(20);data['requirements'].append(data['requirements'][0].copy())
    p=ngo.post('/projects',json=data).json();o=con.post('/offers',json=offer_payload(25)).json()
    rows=ngo.get(f"/projects/{p['id']}/plan").json()
    assert sum(m['quantity'] for r in rows for m in r['allocations'])==25
    req=ngo.post('/partnerships',json={'requirement_id':p['requirements'][0]['id'],'offer_id':o['id'],'quantity':20}).json()
    c=con.post(f"/partnerships/{req['id']}/accept").json()['commitment']
    con.put(f"/commitments/{c['id']}/delivery",json={'delivered_quantity':5})
    assert ngo.patch(f"/projects/{p['id']}",json={'status':'cancelled'}).status_code==200
    assert con.get('/offers?mine=true').json()[0]['available_capacity']==20
    assert ngo.get(f"/projects/{p['id']}/plan").json()[0]['allocations']==[]
    assert ngo.get('/dashboard').json()['unmet']==[]

def test_stale_request_capacity_and_verification(setup):
    client,_=setup;ngo,con,p,o=make(client)
    req=ngo.post('/partnerships',json={'requirement_id':p['requirements'][0]['id'],'offer_id':o['id'],'quantity':15}).json()
    con.put(f"/offers/{o['id']}",json=offer_payload(10))
    assert con.post(f"/partnerships/{req['id']}/accept").status_code==409
    assert client(5).post('/admin/organizations/2/verification',json={'status':'rejected'}).status_code==200
    assert ngo.get(f"/requirements/{p['requirements'][0]['id']}/matches").json()==[]
    response=con.put('/organizations/2',json={'name':'Updated contributor','organization_type':'company','location':'Hyderabad'})
    assert response.status_code==200
    assert response.json()['verification_status']=='rejected'

def test_registration_login_and_real_account_not_demo(setup):
    client,_=setup;c=TestClient(app)
    payload={'name':'Test Organizer','email':'new@example.com','password':'a-long-test-password','role':'ngo','organization':{'name':'New organization','organization_type':'ngo','location':'Hyderabad'}}
    response=c.post('/auth/register',json=payload);assert response.status_code==201
    uid=response.json()['id']
    assert c.get('/auth/me').json()['email']=='new@example.com'
    c.post('/auth/logout');assert c.get('/auth/me').status_code==401
    assert c.post('/auth/login',json={'email':'new@example.com','password':'wrong'}).status_code==401
    assert c.post('/auth/login',json={'email':'new@example.com','password':'a-long-test-password'}).status_code==200
    assert c.post('/auth/register',json=payload).status_code==409
    assert c.post(f'/auth/demo/{uid}').status_code==403

def test_funding_metrics_keep_units_separate(setup):
    client,_=setup;ngo,con=client(1),client(2)
    p=ngo.post('/projects',json=project_payload(30000,'Funding','INR')).json();o=con.post('/offers',json=offer_payload(30000,'Funding','INR')).json()
    req=ngo.post('/partnerships',json={'requirement_id':p['requirements'][0]['id'],'offer_id':o['id'],'quantity':30000}).json()
    c=con.post(f"/partnerships/{req['id']}/accept").json()['commitment']
    con.put(f"/commitments/{c['id']}/delivery",json={'delivered_quantity':10000})
    d=ngo.get('/dashboard').json()
    assert d['funding_committed']==30000 and d['funding_delivered']==10000
    assert d['volunteers_committed']==0 and d['volunteers_deployed']==0
