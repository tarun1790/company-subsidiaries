import re
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from app.agents.state import AgentState
from app.agents.llm import get_llm
from app.core.logging import logger

def get_base_name_key(name: str) -> str:
    """Deterministic fast-path key generator that strips legal endings and punctuation."""
    n = name.lower().strip()
    n = re.sub(r"[^\w\s]", "", n)
    endings = {"ltd", "limited", "llc", "gmbh", "inc", "corp", "co", "plc", "bv", "sa", "pty", "sarl", "ag", "pvt", "private", "company"}
    words = n.split()
    base_words = [w for w in words if w not in endings]
    return " ".join(base_words) if base_words else n

async def entity_normalization_agent(state: AgentState) -> AgentState:
    """Agent 10: Reconciles entity name variants using fast-path deterministic base key grouping."""
    subs = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    
    if not subs:
        return state
        
    logs.append(f"Running Fast Deterministic Entity Normalization for {len(subs)} candidate entities...")
    logger.info(f"Executing Fast Entity Normalization for {len(subs)} entities...")
    
    # Fast-Path: Deterministic Base Key Grouping
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    parent_name = state.get("company_info", {}).get("legal_name") or state["query"]
    from app.agents.cost_optimizer import CostOptimizer
    
    for sub in subs:
        raw_name = sub.get("name", "").strip()
        if not CostOptimizer.is_valid_entity_name(raw_name, parent_name):
            continue
        base_key = get_base_name_key(raw_name)
        if base_key not in grouped:
            grouped[base_key] = []
        grouped[base_key].append(sub)

    normalized_subs = []
    for base_key, items in grouped.items():
        # Pick the most complete/formal legal name as the canonical representative
        canonical_item = max(items, key=lambda x: len(x.get("name", "")))
        canonical_name = canonical_item["name"]
        
        # Merge all evidences across grouped items
        evidences = []
        seen_ev = set()
        for it in items:
            for ev in it.get("evidences", []):
                ev_key = f"{ev.get('source_type')}:{ev.get('source_url')}"
                if ev_key not in seen_ev:
                    seen_ev.add(ev_key)
                    evidences.append(ev)
                    
        country = next((it.get("country") for it in items if it.get("country") and it.get("country") != "Global"), canonical_item.get("country") or "Global")
        relationship_type = next((it.get("relationship_type") for it in items if it.get("relationship_type")), canonical_item.get("relationship_type") or "Subsidiary")
        ownership = next((it.get("ownership") for it in items if it.get("ownership")), canonical_item.get("ownership") or "Wholly-owned")
        confidence = max(float(it.get("confidence") or 0.80) for it in items)

        normalized_subs.append({
            "name": canonical_name,
            "legal_name": canonical_name,
            "country": country,
            "ownership": ownership,
            "relationship_type": relationship_type,
            "registration_number": canonical_item.get("registration_number"),
            "confidence": confidence,
            "notes": f"Grouped {len(items)} source variants via base key '{base_key}'.",
            "evidences": evidences
        })

    logs.append(f"Entity Normalization finished: Reconciled {len(subs)} candidates into {len(normalized_subs)} canonical entities.")
    return {
        **state,
        "subsidiaries": normalized_subs,
        "logs": logs
    }
