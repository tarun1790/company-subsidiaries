import os
import json
from app.agents.state import AgentState
from app.core.logging import logger

def load_scoring_config() -> dict:
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "scoring_config.json")
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load scoring_config.json: {str(e)}")
    
    return {
        "source_authority": {
          "sec_filings": 0.50,
          "public_registry": 0.40,
          "annual_report_pdf": 0.45,
          "official_website": 0.30,
          "dns_ssl_verification": 0.20,
          "web_research": 0.10
        },
        "parameters": {
          "cross_validation_bonus": 0.15,
          "min_confidence": 0.05,
          "max_confidence": 1.0,
          "conflict_penalty": 0.25
        }
    }

async def confidence_scoring_agent(state: AgentState) -> AgentState:
    """Agent 12: Dynamically computes multi-factor confidence scores using configuration constants."""
    subs = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    
    if not subs:
        return state
        
    logs.append("Running Confidence Scoring Agent...")
    logger.info(f"Confidence Scoring Agent processing {len(subs)} entities.")
    
    config = load_scoring_config()
    auth = config["source_authority"]
    params = config["parameters"]
    
    scored_subs = []
    
    for sub in subs:
        evidences = sub.get("evidences", [])
        source_types = set([ev["source_type"] for ev in evidences])
        
        confidence = 0.0
        
        if "SEC Filings" in source_types:
            confidence += auth.get("sec_filings", 0.50)
        if "Public Registry" in source_types:
            confidence += auth.get("public_registry", 0.40)
        if "Annual Report PDF" in source_types:
            confidence += auth.get("annual_report_pdf", 0.45)
        if "Official Website" in source_types:
            confidence += auth.get("official_website", 0.30)
        if "DNS/SSL Verification" in source_types:
            confidence += auth.get("dns_ssl_verification", 0.20)
        if "Web Research" in source_types:
            confidence += auth.get("web_research", 0.10)
            
        if len(source_types) > 1:
            confidence += params.get("cross_validation_bonus", 0.15) * (len(source_types) - 1)
            
        if sub.get("conflict_detected"):
            confidence -= params.get("conflict_penalty", 0.25)
            
        confidence = min(max(confidence, params.get("min_confidence", 0.05)), params.get("max_confidence", 1.0))
        
        sub["confidence"] = confidence
        
        if confidence >= 0.50:
            scored_subs.append(sub)
            
    scored_subs.sort(key=lambda x: (-x["confidence"], x["name"]))
    
    logs.append(f"Confidence scoring complete. Loaded weights dynamically. Retained {len(scored_subs)} entities.")
    return {
        **state,
        "subsidiaries": scored_subs,
        "logs": logs
    }
