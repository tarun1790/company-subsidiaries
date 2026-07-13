from app.agents.state import AgentState
from app.core.logging import logger

async def confidence_scoring_agent(state: AgentState) -> AgentState:
    """Agent 12: Computes cumulative confidence scores based on evidence sources and cross-citations."""
    subs = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    
    if not subs:
        return state
        
    logs.append("Running Confidence Scoring Agent...")
    logger.info(f"Confidence Scoring Agent processing {len(subs)} entities.")
    
    scored_subs = []
    
    for sub in subs:
        evidences = sub.get("evidences", [])
        source_types = set([ev["source_type"] for ev in evidences])
        
        confidence = 0.0
        
        # 1. Base weights from sources
        if "SEC Filings" in source_types:
            confidence += 0.50
        if "Official Website" in source_types:
            confidence += 0.30
        if "Public Registry" in source_types:
            confidence += 0.25
        if "Annual Report PDF" in source_types:
            confidence += 0.40
        if "Web Research" in source_types:
            confidence += 0.10
        if "DNS/SSL Verification" in source_types:
            confidence += 0.15 # Bump for DNS validation
            
        # 2. Cross-citation bump
        if len(source_types) > 1:
            confidence += 0.15 * (len(source_types) - 1)
            
        confidence = min(max(confidence, 0.05), 1.0)
        
        # 3. Classify confidence levels
        sub["confidence"] = confidence
        
        # Filter out unverified entities (< 0.50)
        if confidence >= 0.50:
            scored_subs.append(sub)
            
    # Sort by confidence descending
    scored_subs.sort(key=lambda x: (-x["confidence"], x["name"]))
    
    logs.append(f"Confidence scoring complete. Retained {len(scored_subs)} entities (filtered out {len(subs) - len(scored_subs)} unverified items).")
    return {
        **state,
        "subsidiaries": scored_subs,
        "logs": logs
    }
