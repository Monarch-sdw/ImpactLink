from datetime import date
from math import radians, sin, cos, sqrt, atan2
from sqlalchemy import select, func
from .models import Offer, Organization, Requirement, Partnership, Commitment

def committed(db, offer_id=None, requirement_id=None):
    q = select(func.coalesce(func.sum(Commitment.confirmed_quantity), 0)).join(Partnership, Commitment.partnership_id == Partnership.id)
    if offer_id is not None: q = q.where(Partnership.offer_id == offer_id)
    if requirement_id is not None: q = q.where(Partnership.requirement_id == requirement_id)
    return float(db.scalar(q))

def delivered(db, requirement_id):
    return float(db.scalar(select(func.coalesce(func.sum(Commitment.delivered_quantity), 0)).join(Partnership, Commitment.partnership_id == Partnership.id).where(Partnership.requirement_id == requirement_id)))

def distance(a, b):
    if any(v is None for v in [a.latitude, a.longitude, b.latitude, b.longitude]): return None
    p, q = radians(a.latitude), radians(b.latitude)
    h = sin((q-p)/2)**2 + cos(p)*cos(q)*sin(radians(b.longitude-a.longitude)/2)**2
    return 6371 * 2 * atan2(sqrt(h), sqrt(max(0, 1-h)))

def rank(db, project, requirement, reserved=None):
    if project.status != 'active' or project.end_date < date.today() or requirement.required_end < date.today(): return []
    owner = db.get(Organization, project.organizer_id)
    if owner.verification_status == 'rejected': return []
    remaining = max(0, requirement.quantity - committed(db, requirement_id=requirement.id))
    if not remaining: return []
    matches = []
    for offer in db.scalars(select(Offer).where(Offer.resource_type == requirement.resource_type, Offer.unit == requirement.unit, Offer.status == 'active')):
        org = db.get(Organization, offer.organization_id)
        if org.id == project.organizer_id or org.verification_status == 'rejected': continue
        # Medical resources and healthcare skills require manual verification even in demo mode.
        if (requirement.resource_type == 'Medical resources' or 'healthcare' in requirement.specifications) and org.verification_status != 'verified': continue
        if not set(requirement.specifications).issubset(set(offer.specifications)): continue
        if offer.available_start > requirement.required_start or offer.available_end < requirement.required_end: continue
        capacity = offer.total_capacity - committed(db, offer_id=offer.id) - (reserved or {}).get(offer.id, 0)
        if capacity <= 0: continue
        km = distance(project, offer)
        independent = offer.remote or offer.resource_type == 'Funding'
        if not independent and (km is None or km > offer.service_radius): continue
        compatibility = 1.0 if project.sdg in org.supported_sdgs else 0.7
        proximity = 1.0 if independent else max(0, 1 - km / max(offer.service_radius, 0.001))
        components = {'compatibility': compatibility, 'capacity': min(1, capacity / remaining), 'availability': 1.0, 'proximity': proximity, 'reliability': 1.0 if org.verification_status == 'verified' else 0.3}
        score = round(100 * sum(components[k]*w for k,w in [('compatibility',.35),('capacity',.20),('availability',.20),('proximity',.15),('reliability',.10)]), 1)
        matches.append({'offer_id': offer.id, 'organization_id': org.id, 'organization_name': org.name, 'verification_status': org.verification_status, 'resource_type': offer.resource_type, 'unit': offer.unit, 'capacity': round(capacity, 6), 'score': score, 'components': components, 'distance_km': round(km,1) if km is not None and not independent else None, 'available_start': str(offer.available_start), 'available_end': str(offer.available_end), 'conditions': offer.conditions, 'reasons': [f'Supports SDG {project.sdg}.' if compatibility == 1 else 'Resource and mandatory specifications match; cause preference differs.', f'Can provide {min(capacity, remaining):g} of {remaining:g} remaining {offer.unit}.', 'Available for the full requested date window.', 'Location-independent resource.' if independent else f'{km:.1f} km away, within {offer.service_radius:g} km service radius.', 'Manually verified (simulated for demo records).' if org.verification_status == 'verified' else 'Verification pending; reliability is not established.']})
    return sorted(matches, key=lambda m: (-m['score'], m['offer_id']))

def plan(db, project):
    result, reserved = [], {}
    for req in db.scalars(select(Requirement).where(Requirement.project_id == project.id).order_by(Requirement.id)):
        remaining = max(0, req.quantity - committed(db, requirement_id=req.id))
        matches = rank(db, project, req, reserved)
        allocations = []
        for match in matches:
            if remaining <= 0: break
            qty = min(remaining, match['capacity'])
            allocations.append({**match, 'quantity': qty})
            reserved[match['offer_id']] = reserved.get(match['offer_id'], 0) + qty
            remaining = round(remaining - qty, 6)
        result.append({'requirement_id': req.id, 'resource_type': req.resource_type, 'unit': req.unit, 'requested': req.quantity, 'committed': committed(db, requirement_id=req.id), 'delivered': delivered(db, req.id), 'allocations': allocations, 'shortage': remaining})
    return result
