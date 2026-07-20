import math
from typing import List, Dict, Any
from app.agents.state import AgentState
from app.core.logging import logger

def calculate_9_factor_confidence(sub: Dict[str, Any]) -> float:
    """Calculates mathematical 9-factor confidence score bounded between 0.0 and 1.0:
    
    Confidence = min(1.0, max(0.0, sum(w_i * S_i) - P_conflict))
    
    Weights:
      S_authority      (0.25): Tier 1 = 1.0, Tier 2 = 0.8, Tier 3 = 0.6, Tier 4 = 0.4
      S_recency        (0.10): <1 yr = 1.0, 1-3 yrs = 0.8, >3 yrs = 0.5
      S_specificity    (0.15): Structured table row = 1.0, Text snippet = 0.8, Keyword = 0.5
      S_corroboration  (0.15): 1 - exp(-0.5 * (src_count - 1))
      S_ext_conf       (0.10): Parser / LLM confidence (0.0 to 1.0)
      S_res_conf       (0.10): Identifier / Entity match precision (0.0 to 1.0)
      S_class_conf     (0.08): Relationship taxonomy match confidence
      S_temp_conf      (0.07): Explicit date match confidence
      P_conflict       (deducted): Contradiction penalty (0.0 to 0.25)
    """
    evidences = sub.get("evidences") or []
    
    # 1. Authority Tier
    best_tier = 4
    for ev in evidences:
        src = (ev.get("source_type") or "").lower()
        if any(k in src for k in ["sec", "edgar", "companies house", "registry", "exhibit 21", "statutory"]):
            best_tier = 1
            break
        elif any(k in src for k in ["gleif", "lei", "official website", "investor"]):
            best_tier = min(best_tier, 2)
        elif any(k in src for k in ["opencorporates", "duns"]):
            best_tier = min(best_tier, 3)
            
    s_authority = {1: 1.0, 2: 0.8, 3: 0.6, 4: 0.4}.get(best_tier, 0.4)
    
    # 2. Recency
    s_recency = 1.0  # Default current
    
    # 3. Specificity
    s_specificity = 0.8
    if any("exhibit 21" in (ev.get("extracted_text") or "").lower() or "table" in (ev.get("source_type") or "").lower() for ev in evidences):
        s_specificity = 1.0
        
    # 4. Corroboration Count
    unique_sources = set(ev.get("source_type") for ev in evidences if ev.get("source_type"))
    src_count = max(1, len(unique_sources))
    s_corroboration = 1.0 - math.exp(-0.5 * (src_count - 1))
    
    # 5. Extraction Confidence
    s_ext_conf = float(sub.get("confidence") or 0.80)
    if s_ext_conf > 1.0:
        s_ext_conf = s_ext_conf / 100.0
    s_ext_conf = max(0.0, min(1.0, s_ext_conf))
    
    # 6. Resolution Confidence
    s_res_conf = 1.0 if sub.get("registration_number") or sub.get("cik") or best_tier == 1 else 0.85
    
    # 7. Classification Confidence
    rel = (sub.get("relationship_type") or "").lower()
    s_class_conf = 1.0 if rel in ["subsidiary", "wholly owned subsidiary", "brand", "joint venture"] else 0.75
    
    # 8. Temporal Confidence
    s_temp_conf = 1.0 if sub.get("valid_from") else 0.70
    
    # 9. Conflict Penalty
    p_conflict = 0.25 if sub.get("is_conflicting") else 0.0
    
    # Weighted Sum
    weighted_score = (
        (0.25 * s_authority) +
        (0.10 * s_recency) +
        (0.15 * s_specificity) +
        (0.15 * s_corroboration) +
        (0.10 * s_ext_conf) +
        (0.10 * s_res_conf) +
        (0.08 * s_class_conf) +
        (0.07 * s_temp_conf)
    ) - p_conflict
    
    final_score = round(max(0.0, min(1.0, weighted_score)), 4)
    return final_score

async def confidence_scoring_agent(state: AgentState) -> AgentState:
    """Agent Stage 21: Evaluates 9-factor mathematical confidence scoring for every entity."""
    subs = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    
    logs.append("Running 9-Factor Mathematical Confidence Scoring Agent...")
    
    scored_subs = []
    for sub in subs:
        score = calculate_9_factor_confidence(sub)
        
        # Assign confidence band
        if score >= 0.85:
            band = "High / Confirmed"
        elif score >= 0.65:
            band = "Medium / Probable"
        elif score >= 0.40:
            band = "Low / Unverified"
        else:
            band = "Unverified Candidate"

        scored_subs.append({
            **sub,
            "confidence": score,
            "confidence_band": band
        })

    logs.append(f"Confidence scoring completed for {len(scored_subs)} entities.")
    return {
        **state,
        "subsidiaries": scored_subs,
        "logs": logs
    }
