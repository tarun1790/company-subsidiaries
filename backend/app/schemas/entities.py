from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class CandidateEntity(BaseModel):
    candidate_id: str
    raw_name: str
    normalized_name: Optional[str] = None
    status: str = "Unknown"
    reason: Optional[str] = None
    source_document_id: Optional[str] = None
    source_url: Optional[str] = None
    page_number: Optional[int] = None
    extracted_quote: Optional[str] = None
    extraction_method: Optional[str] = None
    confidence: float = 0.0
    retained_for_audit: bool = True
    should_process_expensively: bool = True
    evidence_ids: List[str] = []
    conflicts: List[Dict[str, Any]] = []

class EvidenceClaim(BaseModel):
    claim_id: str
    entity_name: str
    field_name: str
    field_value: Any
    source_type: str
    source_tier: int
    source_url: Optional[str] = None
    document_title: Optional[str] = None
    page_number: Optional[int] = None
    extracted_quote: Optional[str] = None
    extraction_confidence: float = 0.0
    retrieved_at: str
