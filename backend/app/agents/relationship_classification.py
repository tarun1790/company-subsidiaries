import re
from typing import Dict, List, Any
from app.agents.state import AgentState
from app.core.logging import logger

async def relationship_classification_agent(state: AgentState) -> AgentState:
    """Agent 10: Classifies verified candidate links into Direct, Indirect, Brand, JV, or Holdings."""
    logs = state.get("logs") or []
    warnings = state.get("warnings") or []
    subs = state.get("subsidiaries") or state.get("normalized_entities") or []
    legal_name = state.get("company_info", {}).get("legal_name") or state.get("query")
    
    logs.append("Running Relationship Classification Agent...")
    
    if not subs:
        msg = "RELATIONSHIP_CLASSIFICATION_ZERO_OUTPUT: No candidate entities available to classify."
        logs.append(msg)
        warnings.append({"stage": "relationship_classification", "code": "ZERO_OUTPUT", "message": msg})
        return {
            "relationships": [],
            "logs": logs,
            "warnings": warnings
        }

    relationships = []
    classified_subs = []
    
    for s in subs:
        name = s.get("name", "")
        name_lower = name.lower()
        ownership = str(s.get("ownership", "")).lower()
        
        if "holding" in name_lower or "securit" in name_lower:
            rel_type = "Holding Company"
        elif "brand" in name_lower or "trade" in name_lower:
            rel_type = "Brand"
        elif "joint" in name_lower or "jv" in name_lower or "venture" in name_lower:
            rel_type = "Joint Venture"
        elif "office" in name_lower or "branch" in name_lower:
            rel_type = "Regional Office"
        elif "acquisition" in name_lower or "acquired" in name_lower:
            rel_type = "Acquired Company"
        elif "operating" in name_lower or "operat" in name_lower:
            rel_type = "Operating Company"
        elif "division" in name_lower or "business" in name_lower:
            rel_type = "Business Unit"
        else:
            if "%" in ownership:
                try:
                    pct = float(re.findall(r'(\d+)', ownership)[0])
                    rel_type = "Minority Investment" if pct < 50 else "Direct Subsidiary"
                except Exception:
                    rel_type = "Direct Subsidiary"
            else:
                rel_type = "Direct Subsidiary"
                
        s["relationship_type"] = rel_type
        classified_subs.append(s)
        
        relationships.append({
            "source": s.get("parent") or legal_name,
            "target": name,
            "relationship_type": rel_type,
            "ownership": s.get("ownership", "100%"),
            "confidence": s.get("confidence", 0.85)
        })

    logs.append(f"Relationship Classification produced {len(relationships)} classified relationship edges.")
    return {
        "subsidiaries": classified_subs,
        "relationships": relationships,
        "logs": logs,
        "warnings": warnings
    }
