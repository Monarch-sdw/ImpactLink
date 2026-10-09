from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, EmailStr, model_validator, field_validator

Resource = Literal['Funding', 'Volunteers', 'Equipment', 'Food and supplies', 'Transportation', 'Venue or facilities', 'Training or expertise', 'Medical resources', 'Other']
class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True, allow_inf_nan=False)

class Location(Schema):
    location: str = Field(min_length=2, max_length=150)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    @model_validator(mode='after')
    def coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Provide both latitude and longitude, or neither.')
        return self

class OrgIn(Location):
    name: str = Field(min_length=2, max_length=200)
    organization_type: Literal['ngo', 'company', 'college', 'supplier']
    description: str = Field(default='', max_length=5000)
    contact: str = Field(default='', max_length=200)
    supported_sdgs: list[int] = Field(default_factory=list, max_length=17)
    @field_validator('supported_sdgs')
    @classmethod
    def sdgs(cls, v):
        if any(n < 1 or n > 17 for n in v): raise ValueError('SDGs must be 1–17.')
        return sorted(set(v))

class OrgOut(OrgIn):
    id: int
    verification_status: str
    is_demo: bool

class Register(Schema):
    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    role: Literal['ngo', 'contributor']
    organization: OrgIn

class Login(Schema):
    email: EmailStr
    password: str

class ResourceBase(Schema):
    resource_type: Resource
    unit: str = Field(min_length=1, max_length=40)
    specifications: list[str] = Field(default_factory=list, max_length=30)
    @field_validator('specifications')
    @classmethod
    def tags(cls, v): return sorted({s.strip().lower() for s in v if s.strip()})
    @model_validator(mode='after')
    def units(self):
        self.unit = self.unit.upper() if self.resource_type == 'Funding' else self.unit.lower()
        if self.resource_type == 'Funding' and self.unit != 'INR': raise ValueError('Funding must use INR.')
        if self.resource_type == 'Volunteers' and self.unit != 'people': raise ValueError('Volunteers must use people.')
        return self

class RequirementIn(ResourceBase):
    quantity: float = Field(gt=0, le=1e10)
    required_start: date
    required_end: date
    notes: str = Field(default='', max_length=2000)
    @model_validator(mode='after')
    def dates(self):
        if self.required_end < self.required_start: raise ValueError('Required end must follow start.')
        return self

class ProjectIn(Location):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=10000)
    sdg: int = Field(ge=1, le=17)
    urgency: Literal['Low', 'Medium', 'High', 'Critical'] = 'Medium'
    start_date: date
    end_date: date
    expected_beneficiaries: int = Field(default=0, ge=0)
    requirements: list[RequirementIn] = Field(min_length=1, max_length=30)
    @model_validator(mode='after')
    def dates(self):
        if self.end_date < self.start_date or self.end_date < date.today(): raise ValueError('Project dates must be ordered and end in the future.')
        for r in self.requirements:
            if r.required_start < self.start_date or r.required_end > self.end_date: raise ValueError('Requirement dates must fall within the project timeline.')
        return self

class ProjectPatch(Schema):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=10, max_length=10000)
    status: Literal['active', 'completed', 'cancelled'] | None = None
    update: str | None = Field(default=None, min_length=3, max_length=3000)
    verified_beneficiaries: int | None = Field(default=None, ge=0)
    outcome_evidence: str | None = Field(default=None, max_length=5000)

class OfferIn(ResourceBase, Location):
    total_capacity: float = Field(gt=0, le=1e10)
    available_start: date
    available_end: date
    service_radius: float = Field(default=50, ge=0, le=20000)
    remote: bool = False
    conditions: str = Field(default='', max_length=2000)
    status: Literal['active', 'inactive'] = 'active'
    @model_validator(mode='after')
    def dates(self):
        if self.available_end < self.available_start: raise ValueError('Available end must follow start.')
        return self

class OfferOut(OfferIn):
    id: int
    organization_id: int
    organization_name: str
    available_capacity: float

class RequestIn(Schema):
    requirement_id: int
    offer_id: int
    quantity: float = Field(gt=0, le=1e10)

class DeliveryIn(Schema):
    delivered_quantity: float = Field(ge=0, le=1e10)

class VerifyIn(Schema):
    status: Literal['verified', 'rejected', 'pending']

class UserOut(Schema):
    id: int
    name: str
    email: EmailStr
    role: str
    organization: OrgOut

class RequirementOut(RequirementIn):
    id: int
    project_id: int
    committed: float
    delivered: float
    remaining: float

class ProjectOut(Location):
    id: int
    organizer_id: int
    organization_name: str
    title: str
    description: str
    sdg: int
    urgency: str
    start_date: date
    end_date: date
    status: str
    expected_beneficiaries: int
    verified_beneficiaries: int
    outcome_evidence: str
    is_demo: bool
    progress: int
    requirements: list[RequirementOut]

class CommitmentOut(Schema):
    id: int
    partnership_id: int
    confirmed_quantity: float
    delivered_quantity: float
    status: str

class PartnershipOut(Schema):
    id: int
    project_id: int
    requirement_id: int
    offer_id: int
    requested_quantity: float
    status: str
    project_title: str
    organizer_id: int
    organization_id: int
    organization_name: str
    resource_type: str
    unit: str
    commitment: CommitmentOut | None

class MatchOut(Schema):
    offer_id: int
    organization_id: int
    organization_name: str
    verification_status: str
    resource_type: str
    unit: str
    capacity: float
    score: float
    components: dict[str, float]
    distance_km: float | None
    available_start: date
    available_end: date
    conditions: str
    reasons: list[str]

class AllocationOut(MatchOut):
    quantity: float

class PlanRow(Schema):
    requirement_id: int
    resource_type: str
    unit: str
    requested: float
    committed: float
    delivered: float
    allocations: list[AllocationOut]
    shortage: float
