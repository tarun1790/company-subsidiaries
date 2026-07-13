import re
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from app.agents.state import AgentState
from app.agents.llm import get_llm
from app.core.logging import logger
from langchain_core.prompts import ChatPromptTemplate

class NormalizedEntity(BaseModel):
    original_names: List[str] = Field(description="Original raw names grouped under this entity.")
    normalized_name: str = Field(description="Normalized, clean official legal name.")
    relationship_type: str = Field(description="Inferred classification: Subsidiary, Brand, Acquisition, Division, Parent.")
    relationship_explanation: str = Field(description="Detailed explanation of the relationship inferred from evidence references.")

class VerificationConsensus(BaseModel):
    unified_entities: List[NormalizedEntity] = Field(default=[], description="Reconciled entities list.")

def normalize_name_key(name: str) -> str:
    if not name:
        return ""
    n = name.lower().strip()
    n = re.sub(r"[^\w\s]", "", n)
    endings = ["ltd", "limited", "llc", "gmbh", "inc", "incorporated", "corp", "corporation", "co", "company"]
    words = n.split()
    return " ".join([w for w in words if w not in endings]).strip()

async def verification_agent(state: AgentState) -> AgentState:
    """Agent 7: Evidence Fusion & AI Verification Engine."""
    subs = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    legal_name = state["company_info"].get("legal_name") or state["query"]
    
    logs.append("Executing Evidence Fusion & AI Verification Engine...")
    logger.info(f"Evidence Fusion processing {len(subs)} candidate records.")
    
    if not subs:
        logs.append("No candidates resolved to verify.")
        return state

    # Group candidate references by basic key to deduplicate input sent to LLM
    grouped_inputs: Dict[str, List[Dict[str, Any]]] = {}
    for s in subs:
        if not s.get("name"):
            continue
        key = normalize_name_key(s["name"])
        # Skip ultimate parent match
        if key == normalize_name_key(legal_name) or not key:
            continue
        if key not in grouped_inputs:
            grouped_inputs[key] = []
        grouped_inputs[key].append(s)

    # If no inputs, return
    if not grouped_inputs:
        return {**state, "subsidiaries": [], "logs": logs}

    # Format the evidence matrix for the structured LLM verification query
    evidence_payload = []
    for key, items in grouped_inputs.items():
        ref_lines = []
        for it in items:
            for ev in it.get("evidences", []):
                ref_lines.append(f"  - Source: {ev['source_type']} | Context: {ev.get('extracted_text', 'Verified')}")
        evidence_payload.append(
            f"Candidate: '{items[0]['name']}'\n"
            f"References:\n" + "\n".join(ref_lines)
        )

    evidence_text = "\n\n".join(evidence_payload)

    # Query LLM to normalize and reconcile candidate groups
    llm = get_llm()
    structured_llm = llm.with_structured_output(VerificationConsensus)
    
    system_prompt = (
        "You are an expert Corporate Audit Reconciler and AI Verification Agent.\n"
        "Your task is to review candidate subsidiary references collected from parallel pipelines and reconcile them.\n"
        "RULES:\n"
        "1. NEVER invent any entity or relationship. Reconcile ONLY from the provided candidate references.\n"
        "2. Group items representing the same corporate legal entity, resolving spelling errors or abbreviations.\n"
        "3. Normalize each group to a clean, official legal name.\n"
        "4. Determine the type (Subsidiary, Brand, Acquisition, Division) and write a short explanation of the relationship based on the evidence."
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Ultimate Parent: {parent}\n\nEvidence References to Reconcile:\n{evidence_context}")
    ])

    verified_subs = []
    try:
        chain = prompt | structured_llm
        consensus = await chain.ainvoke({
            "parent": legal_name,
            "evidence_context": evidence_text[:30000] # Safe limit
        })

        # Match consensus unified entities back to their raw source references to compile score and properties
        for ent in consensus.unified_entities:
            # Recompile matching raw entries
            matched_items = []
            normalized_keys = [normalize_name_key(n) for n in ent.original_names]
            
            for key, items in grouped_inputs.items():
                if key in normalized_keys or any(normalize_name_key(it["name"]) in normalized_keys for it in items):
                    matched_items.extend(items)
            
            if not matched_items:
                continue

            # Gather all distinct evidences
            evidences = []
            seen_ev = set()
            for it in matched_items:
                for ev in it.get("evidences", []):
                    ev_key = f"{ev['source_type']}:{ev.get('source_url')}"
                    if ev_key not in seen_ev:
                        seen_ev.add(ev_key)
                        evidences.append(ev)

            # Consolidate country, ownership and registry properties
            country = next((it.get("country") for it in matched_items if it.get("country") and it["country"].lower() not in ["n/a", "unknown", "global", ""]), "Global")
            ownership = next((it.get("ownership") for it in matched_items if it.get("ownership") and it["ownership"] not in ["Not Publicly Disclosed", "Unknown", ""]), "Not Publicly Disclosed")
            reg_num = next((it.get("registration_number") for it in matched_items if it.get("registration_number")), None)

            # Calculate Confidence Score based on source weights
            source_types = set([ev["source_type"] for ev in evidences])
            confidence = 0.0
            if "SEC Filings" in source_types:
                confidence += 0.50
            if "Official Website" in source_types:
                confidence += 0.30
            if "Public Registry" in source_types:
                confidence += 0.25
            if "Web Research" in source_types:
                confidence += 0.10
            if "Annual Report PDF" in source_types:
                confidence += 0.40

            # Cross-citation bump: reward entities verified across multiple pipelines
            if len(source_types) > 1:
                confidence += 0.15 * (len(source_types) - 1)

            confidence = min(max(confidence, 0.05), 1.0)

            # Strict 80%+ confidence verification threshold
            if confidence >= 0.80:
                verified_subs.append({
                    "name": ent.normalized_name,
                    "legal_name": ent.normalized_name,
                    "country": country,
                    "ownership": ownership,
                    "parent": legal_name,
                    "relationship_type": ent.relationship_type,
                    "registration_number": reg_num,
                    "confidence": confidence,
                    "evidences": evidences,
                    "notes": ent.relationship_explanation
                })

    except Exception as e:
        logger.error(f"AI Verification Consensus query failed: {str(e)}")
        logs.append(f"AI Consensus error: {str(e)}. Falling back to deterministic rules.")
        
        # Fallback to simple deterministic rules if LLM fails
        for key, items in grouped_inputs.items():
            best_name = items[0]["name"]
            evidences = []
            seen_ev = set()
            for it in items:
                for ev in it.get("evidences", []):
                    ev_key = f"{ev['source_type']}:{ev.get('source_url')}"
                    if ev_key not in seen_ev:
                        seen_ev.add(ev_key)
                        evidences.append(ev)

            country = next((it.get("country") for it in items if it.get("country")), "Global")
            ownership = next((it.get("ownership") for it in items if it.get("ownership")), "Not Publicly Disclosed")
            reg_num = next((it.get("registration_number") for it in items if it.get("registration_number")), None)
            
            source_types = set([ev["source_type"] for ev in evidences])
            confidence = 0.50 if "SEC Filings" in source_types else 0.30
            if confidence >= 0.80:
                verified_subs.append({
                    "name": best_name,
                    "legal_name": best_name,
                    "country": country,
                    "ownership": ownership,
                    "parent": legal_name,
                    "relationship_type": "Subsidiary",
                    "registration_number": reg_num,
                    "confidence": confidence,
                    "evidences": evidences,
                    "notes": "Deterministic fallback match."
                })

    # Sort subsidiaries by confidence (descending) and name (ascending)
    verified_subs.sort(key=lambda x: (-x["confidence"], x["name"]))
    
    logs.append(f"AI Verification complete. Verified {len(verified_subs)} unique corporate subsidiaries.")
    
    return {
        **state,
        "subsidiaries": verified_subs,
        "logs": logs
    }
