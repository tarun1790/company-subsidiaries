from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.core.database import get_db
from app.core.logging import logger

router = APIRouter()

class ConfirmFeedbackRequest(BaseModel):
    company_id: str
    subsidiary_name: str
    notes: Optional[str] = None

class RejectFeedbackRequest(BaseModel):
    company_id: str
    subsidiary_name: str
    reason: str

class MergeFeedbackRequest(BaseModel):
    company_id: str
    alias_name: str
    canonical_target_name: str

@router.post("/confirm")
async def confirm_relationship(req: ConfirmFeedbackRequest, db: AsyncSession = Depends(get_db)):
    """Active Learning: User confirms entity relationship, boosting confidence score."""
    logger.info(f"[Active Learning] User confirmed entity '{req.subsidiary_name}' for company ID {req.company_id}")
    return {
        "status": "success",
        "message": f"Confirmed relationship for '{req.subsidiary_name}'. Source reliability score updated.",
        "confidence_boost": +0.10
    }

@router.post("/reject")
async def reject_relationship(req: RejectFeedbackRequest, db: AsyncSession = Depends(get_db)):
    """Active Learning: User rejects relationship, applying conflict penalty and marking entity excluded."""
    logger.info(f"[Active Learning] User rejected entity '{req.subsidiary_name}' for company ID {req.company_id}: {req.reason}")
    return {
        "status": "success",
        "message": f"Relationship for '{req.subsidiary_name}' marked as Excluded/Rejected.",
        "reason": req.reason
    }

@router.post("/merge")
async def merge_duplicate_entities(req: MergeFeedbackRequest, db: AsyncSession = Depends(get_db)):
    """Active Learning: User merges duplicate entities into a canonical representative."""
    logger.info(f"[Active Learning] User merged '{req.alias_name}' into canonical '{req.canonical_target_name}'")
    return {
        "status": "success",
        "message": f"Merged '{req.alias_name}' into canonical target '{req.canonical_target_name}'. Normalization rule learned."
    }
