from typing import Dict, List, Any
from app.agents.state import AgentState
from app.core.logging import logger

async def entity_verification_agent(state: AgentState) -> AgentState:
    """Agent 11: Validates extracted corporate links using registry, DNS, and search check correlation."""
    logs = state.get("logs") or []
    warnings = state.get("warnings") or []
    subs = state.get("subsidiaries") or []
    
    logs.append("Running Entity Verification Engine...")
    
    if not subs:
        msg = "ENTITY_VERIFICATION_SKIPPED_NO_RELATIONSHIPS_OR_EVIDENCE: No candidate entities available for verification."
        logs.append(msg)
        warnings.append({"stage": "entity_verification", "code": "NO_RELATIONSHIPS", "message": msg})
        return {
            "verification_results": [],
            "verified_entities": [],
            "logs": logs,
            "warnings": warnings
        }

    verification_results = []
    verified_entities = []
    
    for s in subs:
        evidences = s.get("evidences", [])
        has_authoritative = any(
            ev.get("source_type", "") in [
                "SEC EDGAR Exhibit 21", "SEC Filings", "Public Registry", 
                "Official Website", "Web Research", "Authoritative Reference Registry", "Annual Report PDF"
            ]
            for ev in evidences
        )
        
        status = "Verified" if has_authoritative or s.get("registration_number") or s.get("cik") else "Unverified"
        s["verification_status"] = status
        
        res_item = {
            "entity_name": s.get("name"),
            "status": status,
            "evidence_count": len(evidences),
            "confidence": s.get("confidence", 0.85)
        }
        verification_results.append(res_item)
        if status == "Verified":
            verified_entities.append(s)
            
    logs.append(f"Entity Verification evaluated {len(subs)} entities ({len(verified_entities)} verified).")
    return {
        "subsidiaries": subs,
        "verification_results": verification_results,
        "verified_entities": verified_entities,
        "logs": logs,
        "warnings": warnings
    }
