import re
import uuid
import time
from typing import Dict, List, Any
from app.agents.state import AgentState, emit_node_telemetry
from app.core.logging import logger

SOURCE_AUTHORITY = {
    "sec_filing": 1.00,
    "statutory_registry": 0.95,
    "audited_annual_report": 0.95,
    "gleif": 0.85,
    "official_website": 0.75,
    "opencorporates": 0.70,
    "financial_news": 0.55,
    "wikidata": 0.35,
    "dbpedia": 0.35,
    "unknown": 0.25,
}

def get_base_name_key(name: str) -> str:
    if not name:
        return ""
    n = name.lower().strip()
    n = re.sub(r"[^\w\s]", "", n)
    endings = ["ltd", "limited", "llc", "gmbh", "inc", "incorporated", "corp", "corporation", "co", "company", "sa", "sarl", "as", "ab", "bv", "ag", "kft", "sro", "spa", "pty"]
    words = n.split()
    base = " ".join([w for w in words if w not in endings]).strip()
    suffix = next((w for w in words if w in endings), "")
    return f"{base}_{suffix}" if suffix else base

def detect_field_conflict(values: list, field: str) -> bool:
    clean_values = [v for v in values if v is not None and str(v).strip() != "" and str(v).lower() not in ["n/a", "unknown", "not publicly disclosed"]]
    if len(clean_values) <= 1:
        return False
    if field == "ownership_percentage":
        nums = []
        for v in clean_values:
            try:
                nums.append(float(str(v).replace('%', '')))
            except ValueError:
                pass
        return max(nums) - min(nums) > 0.5 if nums else False
    return len(set(str(v).strip().lower() for v in clean_values)) > 1

def calculate_claim_confidence(source_type: str, extraction_confidence: float, corroboration_count: int, has_conflict: bool) -> float:
    authority = SOURCE_AUTHORITY.get(source_type.lower(), SOURCE_AUTHORITY["unknown"])
    corroboration = min(1.0, 0.35 + (0.15 * max(0, corroboration_count - 1)))
    conflict_penalty = 0.25 if has_conflict else 0.0
    score = (0.50 * authority) + (0.30 * extraction_confidence) + (0.20 * corroboration) - conflict_penalty
    return max(0.0, min(1.0, score))

async def evidence_fusion_agent(state: AgentState) -> AgentState:
    """Agent 9: Consolidates evidence, tracks field-level conflicts, and computes dynamic confidence scores."""
    start_time = time.time()
    logs = state.get("logs", [])
    warnings = state.get("warnings", [])
    legal_name = state["company_info"].get("legal_name") or state["query"]
    
    logs.append("Running Evidence Fusion Agent...")
    
    subs = []
    subs.extend(state.get("sec_results") or [])
    subs.extend(state.get("website_results") or [])
    subs.extend(state.get("registry_results") or [])
    subs.extend(state.get("search_results") or [])
    subs.extend(state.get("domain_results") or [])
    subs.extend(state.get("extracted_document_results") or [])
    
    # Process CandidateEntity inputs directly
    for candidate in state.get("candidate_entities", []):
        if candidate.get("status") not in ["Excluded", "Dissolved"] and candidate.get("should_process_expensively"):
            subs.append(candidate)
            
    if not subs:
        msg = "EVIDENCE_FUSION_SKIPPED_NO_RAW_CLAIMS: No candidate items available to fuse."
        logs.append(msg)
        warnings.append({"stage": "evidence_fusion", "code": "NO_RAW_CLAIMS", "message": msg})
        emit_node_telemetry("evidence_fusion", state, start_time, "skipped")
        return {**state, "logs": logs, "warnings": warnings}

    parent_key = get_base_name_key(legal_name)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    
    from app.agents.cost_optimizer import CostOptimizer
    
    for sub in subs:
        raw_n = sub.get("name") or sub.get("normalized_name") or sub.get("raw_name")
        if not raw_n:
            continue
        clean_n = CostOptimizer.sanitize_and_clean_entity_name(raw_n, legal_name)
        if not clean_n:
            continue
        key = get_base_name_key(clean_n)
        if not key or key == parent_key:
            continue
        sub["name"] = clean_n
        grouped.setdefault(key, []).append(sub)
        
    fused_subs = []
    fused_claims = []
    evidence_records = []

    for key, items in grouped.items():
        sorted_names = sorted(items, key=lambda x: len(x.get("name") or x.get("raw_name") or ""), reverse=True)
        best_name = sorted_names[0].get("name") or sorted_names[0].get("raw_name")
        
        all_countries = [it.get("country") for it in items]
        all_ownerships = [it.get("ownership") for it in items]
        all_parents = [it.get("parent") for it in items]
        
        country_conflict = detect_field_conflict(all_countries, "country")
        ownership_conflict = detect_field_conflict(all_ownerships, "ownership_percentage")
        
        conflicts = []
        status = "Probable"
        requires_review = False
        
        if country_conflict or ownership_conflict:
            status = "Conflicting"
            requires_review = True
            if country_conflict:
                conflicts.append({
                    "field": "country",
                    "claims": [{"value": c, "source": items[i].get("evidences", [{}])[0].get("source_type")} for i, c in enumerate(all_countries) if c]
                })
            if ownership_conflict:
                conflicts.append({
                    "field": "ownership_percentage",
                    "claims": [{"value": o, "source": items[i].get("evidences", [{}])[0].get("source_type")} for i, o in enumerate(all_ownerships) if o]
                })
                
        # Calculate dynamic confidence
        best_source_type = "unknown"
        for item in items:
            for ev in item.get("evidences", []):
                st = ev.get("source_type", "unknown").lower()
                if SOURCE_AUTHORITY.get(st, 0) > SOURCE_AUTHORITY.get(best_source_type, 0):
                    best_source_type = st
                    
        confidence = calculate_claim_confidence(best_source_type, 0.8, len(items), len(conflicts) > 0)
        if confidence >= 0.85 and not conflicts:
            status = "Confirmed"
        elif confidence < 0.5:
            status = "Unverified"
            
        best_country = next((c for c in all_countries if c and c.lower() not in ["n/a", "unknown", "global"]), "Global")
        best_ownership = next((o for o in all_ownerships if o and o not in ["Not Publicly Disclosed", "Unknown"]), "Not Publicly Disclosed")
        best_parent = next((p for p in all_parents if p), legal_name)
        
        evidences = []
        for item in items:
            for ev in item.get("evidences", []):
                ev_rec = {
                    "claim_id": f"claim_{uuid.uuid4().hex[:8]}",
                    "entity_name": best_name,
                    "field_name": "relationship",
                    "field_value": "subsidiary",
                    "source_type": ev.get("source_type", "unknown"),
                    "source_tier": int(SOURCE_AUTHORITY.get(ev.get("source_type", "unknown").lower(), 0.25) * 10),
                    "source_url": ev.get("source_url"),
                    "extracted_quote": ev.get("extracted_text"),
                    "extraction_confidence": 0.8,
                    "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
                evidences.append(ev)
                evidence_records.append(ev_rec)

        fused_item = {
            "name": best_name,
            "legal_name": best_name,
            "country": best_country,
            "ownership": best_ownership,
            "parent": best_parent,
            "relationship_type": "Subsidiary",
            "confidence": confidence,
            "status": status,
            "conflicts": conflicts,
            "requires_review": requires_review,
            "evidences": evidences,
            "notes": f"Fused from {len(items)} claims. Source Tier: {best_source_type}."
        }
        fused_subs.append(fused_item)
        fused_claims.append({
            "subject": best_parent,
            "predicate": "Subsidiary",
            "object": best_name,
            "country": best_country
        })
        
    emit_node_telemetry("evidence_fusion", state, start_time, "success")
    return {
        **state,
        "subsidiaries": fused_subs,
        "candidate_entities": fused_subs,
        "evidence_records": evidence_records,
        "fused_claims": fused_claims,
        "logs": logs,
        "warnings": warnings
    }
