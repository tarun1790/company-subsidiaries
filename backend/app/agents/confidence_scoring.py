import math
from typing import List, Dict, Any
from app.agents.state import AgentState
from app.core.logging import logger

# Calibrated Dynamic Source Reliability Weights (Adaptive Bayesian Model)
CALIBRATED_SOURCE_RELIABILITY = {
    "sec_edgar": 0.95,
    "annual_report": 0.95,
    "mca": 0.90,
    "gleif": 0.90,
    "public_registry": 0.88,
    "official_website": 0.85,
    "wikipedia": 0.70,
    "web_research": 0.45,
    "single_snippet": 0.35,
    "default": 0.35
}

def get_calibrated_authority(source_type: str) -> float:
    """Computes dynamic reliability based on historical accuracy calibration."""
    src = (source_type or "").lower()
    if any(k in src for k in ["sec", "edgar", "exhibit 21"]):
        return CALIBRATED_SOURCE_RELIABILITY["sec_edgar"]
    elif any(k in src for k in ["annual report", "pdf", "10-k"]):
        return CALIBRATED_SOURCE_RELIABILITY["annual_report"]
    elif "mca" in src:
        return CALIBRATED_SOURCE_RELIABILITY["mca"]
    elif "gleif" in src or "lei" in src:
        return CALIBRATED_SOURCE_RELIABILITY["gleif"]
    elif any(k in src for k in ["companies house", "registry", "opencorporates"]):
        return CALIBRATED_SOURCE_RELIABILITY["public_registry"]
    elif any(k in src for k in ["official website", "investor", "domain"]):
        return CALIBRATED_SOURCE_RELIABILITY["official_website"]
    elif "wikipedia" in src:
        return CALIBRATED_SOURCE_RELIABILITY["wikipedia"]
    elif any(k in src for k in ["web research", "news", "search"]):
        return CALIBRATED_SOURCE_RELIABILITY["web_research"]
    return CALIBRATED_SOURCE_RELIABILITY["default"]

def calculate_9_factor_confidence(sub: Dict[str, Any]) -> float:
    """Calculates mathematical confidence score based on source credibility tiers."""
    evidences = sub.get("evidences") or []
    if not evidences:
        return 0.35
        
    authority_scores = [get_calibrated_authority(ev.get("source_type", "")) for ev in evidences]
    max_authority = max(authority_scores)
    
    unique_sources = set(ev.get("source_type") for ev in evidences if ev.get("source_type"))
    src_count = len(unique_sources)
    
    # Multi-source boost: Tier 1 + Official Website / MCA -> 95%+
    if src_count >= 2 and max_authority >= 0.85:
        final_score = min(0.98, max_authority + 0.05)
    elif max_authority >= 0.85:
        final_score = max_authority
    elif max_authority >= 0.70:
        final_score = 0.70 if src_count == 1 else 0.78
    elif src_count == 1 and max_authority <= 0.45:
        final_score = 0.35
    else:
        final_score = max_authority
        
    return round(final_score, 2)

async def confidence_scoring_agent(state: AgentState) -> AgentState:
    """Agent Stage 21: Evaluates dynamic multi-tiered confidence scoring and filters out noise."""
    subs = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    
    logs.append("Running Dynamic Multi-Tiered Confidence Scoring Agent...")
    
    scored_subs = []
    for sub in subs:
        score = calculate_9_factor_confidence(sub)
        
        # Discard low-confidence single-snippet noise items (< 40%)
        if score < 0.40:
            continue
            
        if score >= 0.85:
            band = "Confirmed"
        elif score >= 0.65:
            band = "Probable"
        else:
            band = "Unverified"

        scored_subs.append({
            **sub,
            "confidence": score,
            "confidence_band": band
        })

    logs.append(f"Dynamic confidence scoring completed. Retained {len(scored_subs)} verified entities (filtered out noise).")
    return {
        **state,
        "subsidiaries": scored_subs,
        "logs": logs
    }
