from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class EvidenceBase(BaseModel):
    source_type: str
    source_url: Optional[str] = None
    extracted_text: Optional[str] = None

class EvidenceCreate(EvidenceBase):
    pass

class EvidenceResponse(EvidenceBase):
    id: UUID
    verified_at: datetime

    class Config:
        from_attributes = True

class SubsidiaryBase(BaseModel):
    name: str
    legal_name: Optional[str] = None
    country: Optional[str] = None
    ownership: Optional[str] = None
    parent: Optional[str] = None
    relationship_type: Optional[str] = None
    registration_number: Optional[str] = None
    confidence: float = 0.0
    notes: Optional[str] = None

class SubsidiaryCreate(SubsidiaryBase):
    pass

class SubsidiaryResponse(SubsidiaryBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    evidences: List[EvidenceResponse] = []

    class Config:
        from_attributes = True
