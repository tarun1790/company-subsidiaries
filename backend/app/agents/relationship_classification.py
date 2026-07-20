import re
from typing import Dict, List, Any
from app.agents.state import AgentState
from app.core.logging import logger

async def relationship_classification_agent(state: AgentState) -> AgentState:
    """Agent 10: Classifies verified candidate links into Direct, Indirect, Brand, JV, or Holdings."""
    logs = state.get("logs") or []
    subs = state.get("subsidiaries") or []
    
    logs.append("Running Relationship Classification Agent...")
    
    for s in subs:
        name = s.get("name", "").lower()
        ownership = str(s.get("ownership", "")).lower()
        
        if "holding" in name or "securit" in name:
            s["relationship_type"] = "Holding Company"
        elif "brand" in name or "trade" in name:
            s["relationship_type"] = "Brand"
        elif "joint" in name or "jv" in name or "venture" in name:
            s["relationship_type"] = "Joint Venture"
        elif "office" in name or "branch" in name:
            s["relationship_type"] = "Regional Office"
        elif "acquisition" in name or "acquired" in name:
            s["relationship_type"] = "Acquired Company"
        elif "operating" in name or "operat" in name:
            s["relationship_type"] = "Operating Company"
        elif "division" in name or "business" in name:
            s["relationship_type"] = "Business Unit"
        else:
            if "%" in ownership:
                try:
                    pct = float(re.findall(r'(\d+)', ownership)[0])
                    if pct < 50:
                        s["relationship_type"] = "Minority Investment"
                    else:
                        s["relationship_type"] = "Direct Subsidiary"
                except Exception:
                    s["relationship_type"] = "Direct Subsidiary"
            else:
                s["relationship_type"] = "Direct Subsidiary"
                
    return {
        **state,
        "subsidiaries": subs,
        "logs": logs
    }
