import re
from typing import List, Dict, Any
from app.agents.state import AgentState
from app.core.logging import logger

def normalize_name(name: str) -> str:
    """Normalizes corporate names for deduplication."""
    if not name:
        return ""
    n = name.lower().strip()
    # Remove punctuation
    n = re.sub(r"[^\w\s]", "", n)
    # Remove corporate endings
    endings = [
        "ltd", "limited", "llc", "gmbh", "inc", "incorporated", 
        "corp", "corporation", "co", "company", "sa", "sarl", "plc", 
        "bv", "nv", "holding", "holdings", "group", "uk", "usa", "india"
    ]
    words = n.split()
    clean_words = [w for w in words if w not in endings]
    return " ".join(clean_words).strip()

async def verification_agent(state: AgentState) -> AgentState:
    """Agent 7: Combines all subsidiary inputs, merges duplicate entities, and calculates confidence scores."""
    subs = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    legal_name = state["company_info"].get("legal_name") or state["query"]
    
    logs.append("Running Verification Agent (Deduplication, Entity Normalization, Evidence Consolidation)...")
    logger.info(f"Verification Agent processing {len(subs)} raw discoveries.")

    if not subs:
        logs.append("No discovered entities to verify.")
        return state

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    normalized_parent = normalize_name(legal_name)

    # 1. Group entities by normalized name
    for sub in subs:
        sub_name = sub["name"]
        norm = normalize_name(sub_name)
        
        # Skip if name matches the parent company itself
        if norm == normalized_parent or not norm:
            continue
            
        if norm not in grouped:
            grouped[norm] = []
        grouped[norm].append(sub)

    verified_subs = []
    
    # 2. Consolidate groups
    for norm_name, items in grouped.items():
        # Select best representative display name (usually the longest or cleanest)
        sorted_names = sorted(items, key=lambda x: len(x["name"]), reverse=True)
        best_name = sorted_names[0]["name"]
        
        # Consolidate evidence
        evidences: List[Dict[str, Any]] = []
        seen_ev = set()
        
        for item in items:
            for ev in item.get("evidences", []):
                ev_key = f"{ev['source_type']}:{ev.get('source_url')}"
                if ev_key not in seen_ev:
                    seen_ev.add(ev_key)
                    evidences.append(ev)

        # Calculate Confidence Score based on source weights
        # SEC: +50%, Website: +30%, Registry: +20%, Wikipedia/Web research: +10%, other: +5%
        source_types = set([ev["source_type"] for ev in evidences])
        
        confidence = 0.0
        if "SEC Filings" in source_types:
            confidence += 0.50
        if "Official Website" in source_types:
            confidence += 0.30
        if "Public Registry" in source_types:
            confidence += 0.20
        if "Web Research" in source_types:
            confidence += 0.10
        if "Annual Report PDF" in source_types:
            confidence += 0.40 # Higher than website, close to SEC
            
        # Bound confidence between 0.05 (minimum) and 1.0 (maximum)
        confidence = min(max(confidence, 0.05), 1.0)

        # Consolidate country code
        # Prioritize registry or SEC country details
        country = None
        for item in items:
            if item.get("country") and item["country"].lower() not in ["n/a", "unknown", ""]:
                # If SEC or registry provides country, pick it
                country = item["country"]
                break
        if not country:
            country = "Global"

        # Consolidate ownership
        ownership = "100%"
        for item in items:
            if item.get("ownership") and item["ownership"] != "100%":
                ownership = item["ownership"]
                break

        # Select first available registration number
        reg_num = next((item.get("registration_number") for item in items if item.get("registration_number")), None)
        
        # Select relationship type
        rel_type = "Subsidiary"
        for item in items:
            if item.get("relationship_type") and item["relationship_type"] != "Subsidiary":
                rel_type = item["relationship_type"]
                break

        # Select notes
        notes = items[0].get("notes") or f"Verified entity resolved from {len(evidences)} sources."

        verified_subs.append({
            "name": best_name,
            "legal_name": best_name,
            "country": country,
            "ownership": ownership,
            "parent": legal_name,
            "relationship_type": rel_type,
            "registration_number": reg_num,
            "confidence": confidence,
            "evidences": evidences,
            "notes": notes
        })

    # Sort subsidiaries by confidence (descending) and name (ascending)
    verified_subs.sort(key=lambda x: (-x["confidence"], x["name"]))
    
    logs.append(f"Verification complete. Resolved {len(verified_subs)} unique corporate subsidiaries.")
    
    return {
        **state,
        "subsidiaries": verified_subs,
        "logs": logs
    }
