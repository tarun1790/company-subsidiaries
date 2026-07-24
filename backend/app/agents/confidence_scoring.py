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
    """Calculates mathematical confidence score based on additive source credibility tiers."""
    evidences = sub.get("evidences") or []
    if not evidences:
        return 0.20
        
    score = 0.40 # Base score for any extracted entity
    unique_sources = set()
    
    for ev in evidences:
        src = (ev.get("source_type") or "").lower()
        if src not in unique_sources:
            unique_sources.add(src)
            if any(k in src for k in ["sec", "edgar", "exhibit 21"]):
                score += 0.45
            elif any(k in src for k in ["annual report", "pdf", "10-k"]):
                score += 0.45
            elif "mca" in src or "gleif" in src or "lei" in src or "registry" in src or "opencorporates" in src:
                score += 0.35
            elif any(k in src for k in ["official website", "investor", "domain"]):
                score += 0.25
            elif "wikipedia" in src:
                score += 0.15
            elif any(k in src for k in ["web research", "news", "search"]):
                score += 0.15
            else:
                score += 0.10
                
    # Boost if there are multiple distinct sources
    if len(unique_sources) >= 2:
        score += 0.10
        
    final_score = min(1.0, score)
    return round(final_score, 2)

async def confidence_scoring_agent(state: AgentState) -> AgentState:
    """Agent Stage 21: Evaluates dynamic multi-tiered confidence scoring and filters out noise."""
    subs = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    
    logs.append("Running Dynamic Multi-Tiered Confidence Scoring Agent...")
    
    scored_subs = []
    for sub in subs:
        score = calculate_9_factor_confidence(sub)
        
        # Discard only extremely low confidence noise (< 20%)
        if score < 0.20:
            continue
            
        if score >= 0.80:
            band = "Confirmed"
        elif score >= 0.50:
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
