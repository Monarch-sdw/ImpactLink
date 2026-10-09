from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, Date, DateTime, ForeignKey, JSON, CheckConstraint, UniqueConstraint
from .db import Base

def now():
    return datetime.now(timezone.utc)

class Organization(Base):
    __tablename__ = 'organizations'
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    organization_type = Column(String(30), nullable=False)
    description = Column(Text, default='')
    location = Column(String(150), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    contact = Column(String(200), default='')
    verification_status = Column(String(20), default='pending')
    supported_sdgs = Column(JSON, default=list)
    is_demo = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=now)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    email = Column(String(254), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    organization_id = Column(ForeignKey('organizations.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), default=now)

class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True)
    organizer_id = Column(ForeignKey('organizations.id'), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String(150), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    sdg = Column(Integer, nullable=False)
    urgency = Column(String(20), default='Medium')
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String(20), default='active', index=True)
    expected_beneficiaries = Column(Integer, default=0)
    verified_beneficiaries = Column(Integer, default=0)
    outcome_evidence = Column(Text, default='')
    is_demo = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint('expected_beneficiaries >= 0 AND verified_beneficiaries >= 0'),)

class Requirement(Base):
    __tablename__ = 'requirements'
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey('projects.id'), nullable=False, index=True)
    resource_type = Column(String(40), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(40), nullable=False)
    specifications = Column(JSON, default=list)
    required_start = Column(Date, nullable=False)
    required_end = Column(Date, nullable=False)
    notes = Column(Text, default='')
    __table_args__ = (CheckConstraint('quantity > 0'),)

class Offer(Base):
    __tablename__ = 'offers'
    id = Column(Integer, primary_key=True)
    organization_id = Column(ForeignKey('organizations.id'), nullable=False, index=True)
    resource_type = Column(String(40), nullable=False, index=True)
    total_capacity = Column(Float, nullable=False)
    unit = Column(String(40), nullable=False)
    specifications = Column(JSON, default=list)
    available_start = Column(Date, nullable=False)
    available_end = Column(Date, nullable=False)
    location = Column(String(150), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    service_radius = Column(Float, default=50)
    remote = Column(Boolean, default=False)
    conditions = Column(Text, default='')
    status = Column(String(20), default='active')
    created_at = Column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint('total_capacity > 0 AND service_radius >= 0'),)

class Partnership(Base):
    __tablename__ = 'partnerships'
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey('projects.id'), nullable=False, index=True)
    requirement_id = Column(ForeignKey('requirements.id'), nullable=False, index=True)
    offer_id = Column(ForeignKey('offers.id'), nullable=False, index=True)
    requested_quantity = Column(Float, nullable=False)
    status = Column(String(20), default='pending')
    created_at = Column(DateTime(timezone=True), default=now)
    responded_at = Column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('requirement_id', 'offer_id'), CheckConstraint('requested_quantity > 0'))

class Commitment(Base):
    __tablename__ = 'commitments'
    id = Column(Integer, primary_key=True)
    partnership_id = Column(ForeignKey('partnerships.id'), unique=True, nullable=False)
    confirmed_quantity = Column(Float, nullable=False)
    delivered_quantity = Column(Float, default=0, nullable=False)
    status = Column(String(20), default='committed')
    confirmed_at = Column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint('confirmed_quantity > 0 AND delivered_quantity >= 0 AND delivered_quantity <= confirmed_quantity'),)

class ProjectUpdate(Base):
    __tablename__ = 'project_updates'
    id = Column(Integer, primary_key=True)
    project_id = Column(ForeignKey('projects.id'), nullable=False)
    description = Column(Text, nullable=False)
    update_type = Column(String(30), default='progress')
    created_at = Column(DateTime(timezone=True), default=now)

class Verification(Base):
    __tablename__ = 'verification_records'
    id = Column(Integer, primary_key=True)
    organization_id = Column(ForeignKey('organizations.id'), nullable=False)
    reviewer_id = Column(ForeignKey('users.id'), nullable=False)
    status = Column(String(20), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), default=now)

class Recommendation(Base):
    __tablename__ = 'recommendations'
    id = Column(Integer, primary_key=True)
    requirement_id = Column(ForeignKey('requirements.id'), nullable=False)
    offer_id = Column(ForeignKey('offers.id'), nullable=False)
    score = Column(Float, nullable=False)
    __table_args__ = (UniqueConstraint('requirement_id', 'offer_id'),)

class Volunteer(Base):
    __tablename__ = 'volunteers'
    id = Column(Integer, primary_key=True)
    organization_id = Column(ForeignKey('organizations.id'), nullable=False)
    display_name = Column(String(150), nullable=False)
    skills = Column(JSON, default=list)
    is_demo = Column(Boolean, default=True)
