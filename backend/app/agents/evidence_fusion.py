import re
from typing import Dict, List, Any
from app.agents.state import AgentState
from app.core.logging import logger

def get_base_name_key(name: str) -> str:
    if not name:
        return ""
    n = name.lower().strip()
    n = re.sub(r"[^\w\s]", "", n)
    endings = ["ltd", "limited", "llc", "gmbh", "inc", "incorporated", "corp", "corporation", "co", "company", "sa", "sarl", "as", "ab", "bv", "ag", "kft", "sro", "spa", "pty"]
    words = n.split()
    base = " ".join([w for w in words if w not in endings]).strip()
    
    # Extract suffix to differentiate regional legal entities
    suffix = ""
    for w in words:
        if w in endings:
            suffix = w
            break
    return f"{base}_{suffix}" if suffix else base

async def evidence_fusion_agent(state: AgentState) -> AgentState:
    """Agent 9: Merges duplicate corporate entities, groups evidence trail matrices."""
    logs = state.get("logs", [])
    legal_name = state["company_info"].get("legal_name") or state["query"]
    
    logs.append("Running Evidence Fusion Agent...")
    
    # Gather candidates from namespaced collector outputs
    subs = []
    subs.extend(state.get("sec_results") or [])
    subs.extend(state.get("website_results") or [])
    subs.extend(state.get("registry_results") or [])
    subs.extend(state.get("search_results") or [])
    subs.extend(state.get("domain_results") or [])
    subs.extend(state.get("extracted_document_results") or [])
    
    logger.info(f"Evidence Fusion Agent consolidating {len(subs)} candidate items from all sources.")
    
    if not subs:
        logs.append("No new subsidiary records found to merge in this iteration.")
        return {
            **state,
            "logs": logs
        }
        
    parent_key = get_base_name_key(legal_name)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    
    # Group candidates from current iteration
    for sub in subs:
        name = sub.get("name")
        if not name:
            continue
        if isinstance(name, dict):
            logger.error(f"DEBUG: Found sub with name as dict: {sub}")
            name = name.get("name") or str(name)
        key = get_base_name_key(name)
        if not key:
            continue
            
        # Refined Parent Collision check:
        if key == parent_key:
            n_clean = re.sub(r"[^\w]", "", name.lower())
            p_clean = re.sub(r"[^\w]", "", legal_name.lower())
            if n_clean == p_clean:
                continue
            if len(name.split()) == 1 and name.lower() in legal_name.lower():
                continue
            
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(sub)
        
    # Merge existing subsidiaries from previous iterations
    existing_subs = state.get("subsidiaries") or []
    for sub in existing_subs:
        name = sub.get("name")
        if not name:
            continue
        key = get_base_name_key(name)
        if not key:
            continue
            
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(sub)
        
    fused_subs = []
    for key, items in grouped.items():
        # Select cleanest/longest name as representatives
        sorted_names = sorted(items, key=lambda x: len(x["name"]), reverse=True)
        best_name = sorted_names[0]["name"]
        
        # Consolidate evidence context lists
        evidences = []
        seen_ev = set()
        for item in items:
            for ev in item.get("evidences", []):
                ev_key = f"{ev['source_type']}:{ev.get('source_url')}"
                if ev_key not in seen_ev:
                    seen_ev.add(ev_key)
                    evidences.append(ev)
                    
        # Consolidate basic fields
        country = next((it.get("country") for it in items if it.get("country") and it["country"].lower() not in ["n/a", "unknown", "global", ""]), "Global")
        ownership = next((it.get("ownership") for it in items if it.get("ownership") and it["ownership"] not in ["Not Publicly Disclosed", "Unknown", ""]), "Not Publicly Disclosed")
        reg_num = next((it.get("registration_number") for it in items if it.get("registration_number")), None)
        rel_type = next((it.get("relationship_type") for it in items if it.get("relationship_type") and it["relationship_type"] != "Subsidiary"), "Subsidiary")
        parent_name = next((it.get("parent") for it in items if it.get("parent")), legal_name)
        
        fused_subs.append({
            "name": best_name,
            "legal_name": best_name,
            "country": country,
            "ownership": ownership,
            "parent": parent_name,
            "relationship_type": rel_type,
            "registration_number": reg_num,
            "confidence": 0.0, # Will be set by scoring agent
            "evidences": evidences,
            "notes": items[0].get("notes") or "Fused candidate entity."
        })
        
    logs.append(f"Evidence Fusion consolidated candidates count: {len(fused_subs)} (down from {len(subs) + len(existing_subs)}).")
    return {
        **state,
        "subsidiaries": fused_subs,
        "logs": logs
    }
