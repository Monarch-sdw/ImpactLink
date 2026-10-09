from datetime import date, timedelta
import secrets
from pwdlib import PasswordHash
from sqlalchemy import select
from .db import SessionLocal
from .models import Organization, User, Project, Requirement, Offer, Volunteer

def seed(db):
    if db.scalar(select(Organization.id).limit(1)):
        print('Database already contains organizations; seed skipped.'); return
    start=date.today()+timedelta(days=7); end=start+timedelta(days=28)
    names=['Udaan Learning Collective','Sahara Relief Network','Haritha Community Trust','Aarogya Outreach Foundation']
    orgs=[]
    for i in range(90):
        kind='ngo' if i<50 else 'company' if i<70 else 'college' if i<80 else 'supplier'
        name=names[i] if i<4 else f'{["Pragati","Sankalp","Navya","Srujana","Setu"][i%5]} {kind.title()} {i+1:02}'
        org=Organization(name=f'{name} · Demo',organization_type=kind,description='Fictional demonstration organization for ImpactLink. No real-world verification or partnership is implied.',location=['Hyderabad','Secunderabad','Gachibowli'][i%3],latitude=17.385+(i%5)*.015,longitude=78.486+(i%4)*.012,verification_status='verified' if i%7 else 'pending',supported_sdgs=[3,4,11,13,17],is_demo=True)
        db.add(org); orgs.append(org)
    db.flush()
    # Shared contributor offers let judges demonstrate several resource types with one account.
    for index,label,role in [(0,'NGO organizer','ngo'),(50,'CSR contributor','contributor'),(70,'College coordinator','contributor'),(80,'Community supplier','contributor'),(89,'Demo administrator','admin')]:
        db.add(User(name=label,email=f'demo{index}@impactlink.example',password_hash=PasswordHash.recommended().hash(secrets.token_urlsafe(24)),role=role,organization_id=orgs[index].id))
    scenarios=[
      ('Digital futures: a classroom for everyone',4,'High',120,[('Volunteers',20,'people',['tutoring']),('Equipment',15,'laptops',['laptop']),('Funding',30000,'INR',[])]),
      ('Flood relief, together',11,'Critical',500,[('Food and supplies',500,'kits',['food']),('Volunteers',40,'people',[]),('Funding',100000,'INR',[]),('Transportation',4,'trips',[])]),
      ('A greener neighbourhood',13,'Medium',250,[('Other',200,'saplings',['sapling']),('Volunteers',25,'people',[]),('Transportation',2,'trips',[]),('Venue or facilities',1,'sites',['planting'])]),
      ('Community health, closer to home',3,'High',150,[('Volunteers',8,'people',['healthcare']),('Medical resources',6,'kits',['diagnostic']),('Venue or facilities',1,'days',[]),('Funding',20000,'INR',[])])]
    for i in range(30):
        title,sdg,urgency,beneficiaries,needs=scenarios[i%4]
        p=Project(organizer_id=orgs[0 if i<4 else i%50].id,title=title if i<4 else f'{title} — community {i+1}',description=['A four-week digital literacy programme connecting young learners with volunteer tutors, working laptops, and practical skills. Help us build an accessible learning space in Hyderabad.','Coordinate food kits, local volunteers, and transport for families affected by flooding. Each commitment is tracked separately from actual delivery.','Bring neighbours together to plant native trees and create a shared green space. We need saplings, volunteers, transport, and a suitable planting site.','A community health camp providing basic screening and health education. Qualified healthcare volunteers and diagnostic resources require organization verification.'][i%4],location='Hyderabad',latitude=17.385,longitude=78.486,sdg=sdg,urgency=urgency,start_date=start,end_date=end,expected_beneficiaries=beneficiaries,is_demo=True)
        db.add(p); db.flush()
        for category,qty,unit,spec in needs: db.add(Requirement(project_id=p.id,resource_type=category,quantity=qty,unit=unit,specifications=spec,required_start=start,required_end=end))
    offers=[(50,'Funding',65000,'INR',[]),(51,'Funding',50000,'INR',[]),(50,'Equipment',15,'laptops',['laptop']),(70,'Volunteers',15,'people',['tutoring']),(71,'Volunteers',20,'people',['tutoring']),(72,'Volunteers',10,'people',[]),(80,'Food and supplies',300,'kits',['food']),(81,'Food and supplies',200,'kits',['food']),(80,'Transportation',2,'trips',[]),(82,'Other',200,'saplings',['sapling']),(80,'Venue or facilities',1,'sites',['planting']),(50,'Medical resources',4,'kits',['diagnostic']),(70,'Volunteers',5,'people',['healthcare']),(80,'Venue or facilities',1,'days',[])]
    # Contributors without a demo login are still useful in ranked recommendations.
    # Add judge access for each seeded offer owner, with no public password.
    existing={50,70,80,89}
    for idx in sorted({o[0] for o in offers}-existing):
        db.add(User(name=f'{orgs[idx].name} coordinator',email=f'demo{idx}@impactlink.example',password_hash=PasswordHash.recommended().hash(secrets.token_urlsafe(24)),role='contributor',organization_id=orgs[idx].id))
    for idx,category,qty,unit,spec in offers:
        db.add(Offer(organization_id=orgs[idx].id,resource_type=category,total_capacity=qty,unit=unit,specifications=spec,available_start=start-timedelta(days=5),available_end=end+timedelta(days=20),location='Hyderabad',latitude=orgs[idx].latitude,longitude=orgs[idx].longitude,service_radius=60,remote=category=='Funding',conditions='Please coordinate scheduling before delivery. Fictional demo offer.'))
    for i in range(100): db.add(Volunteer(organization_id=orgs[70+i%10].id,display_name=f'Demo volunteer {i+1:03}',skills=['tutoring'] if i%2 else ['community support']))
    db.commit(); print('Seeded 90 fictional organizations, 100 volunteers, 30 projects and 14 offers.')

if __name__=='__main__':
    with SessionLocal() as db: seed(db)
