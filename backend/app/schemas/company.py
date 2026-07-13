from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

class CompanyBase(BaseModel):
    query_name: str
    legal_name: Optional[str] = None
    cik: Optional[str] = None
    ticker: Optional[str] = None
    domain: Optional[str] = None
    hq_country: Optional[str] = None
    metadata_fields: Optional[Dict[str, Any]] = None

class CompanyCreate(CompanyBase):
    pass

class CompanyResponse(CompanyBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True
