from pydantic import BaseModel, Field
from typing import List, Dict, Any
from app.agents.state import AgentState
from app.agents.llm import get_llm
from app.core.logging import logger
from langchain_core.prompts import ChatPromptTemplate

class NormalizedGroup(BaseModel):
    original_names: List[str] = Field(description="List of raw original name variants belonging to this group.")
    normalized_name: str = Field(description="Normalized canonical legal entity name.")

class NormalizationConsensus(BaseModel):
    normalized_entities: List[NormalizedGroup] = Field(default=[], description="Normalized groups.")

async def entity_normalization_agent(state: AgentState) -> AgentState:
    """Agent 10: Reconciles entity name variants using structured AI consensus."""
    subs = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    legal_name = state["company_info"].get("legal_name") or state["query"]
    
    if not subs:
        return state
        
    logs.append("Running Entity Normalization Agent...")
    logger.info("Executing Entity Normalization consensus...")
    
    # 1. Format the candidates payload for LLM normalizer
    candidate_names = [s["name"] for s in subs]
    
    llm = get_llm(capability="classification")
    structured_llm = llm.with_structured_output(NormalizationConsensus)
    
    system_prompt = (
        "You are an expert Corporate entity registry reconciler.\n"
        "Your task is to review candidate company name variants and group duplicates representing the same legal entity.\n"
        "RULES:\n"
        "1. Reconcile ONLY from the provided candidate names list.\n"
        "2. Resolve typographical errors, regional variants, and missing endings (e.g. 'Acme UK' / 'Acme Services UK Limited' -> 'Acme Services UK Limited').\n"
        "3. For each group, output a single normalized canonical legal name."
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Ultimate Parent: {parent}\nCandidate Names List:\n{names}")
    ])
    
    try:
        chain = prompt | structured_llm
        consensus = await chain.ainvoke({
            "parent": legal_name,
            "names": "\n".join([f"- {n}" for n in candidate_names])
        })
        
        normalized_subs = []
        import re
        suffixes = {"inc", "llc", "ltd", "corp", "co", "plc", "gmbh", "ag", "sa", "bv", "nv", "sarl", "as", "pvt", "private", "limited", "company"}
        processed_original_names = set()
        
        for group in consensus.normalized_entities:
            norm_lower = re.sub(r'[^\w\s]', '', group.normalized_name).strip().lower()
            if norm_lower in suffixes or len(norm_lower) < 3:
                continue
                
            matched_items = []
            for sub in subs:
                sub_clean = sub["name"].strip().lower()
                orig_cleans = [o.strip().lower() for o in group.original_names]
                if sub_clean in orig_cleans or sub_clean == group.normalized_name.strip().lower() or any(sub_clean in oc for oc in orig_cleans):
                    matched_items.append(sub)
                    processed_original_names.add(sub_clean)
                    
            if not matched_items:
                continue
                
            # Merge evidences and notes
            evidences = []
            seen_ev = set()
            for it in matched_items:
                for ev in it.get("evidences", []):
                    ev_key = f"{ev['source_type']}:{ev.get('source_url')}"
                    if ev_key not in seen_ev:
                        seen_ev.add(ev_key)
                        evidences.append(ev)
                        
            country = next((it.get("country") for it in matched_items if it.get("country") and it["country"].lower() not in ["n/a", "unknown", "global", ""]), "Global")
            ownership = next((it.get("ownership") for it in matched_items if it.get("ownership") and it["ownership"] not in ["Not Publicly Disclosed", "Unknown", ""]), "Not Publicly Disclosed")
            reg_num = next((it.get("registration_number") for it in matched_items if it.get("registration_number")), None)
            rel_type = next((it.get("relationship_type") for it in matched_items if it.get("relationship_type") and it["relationship_type"] != "Subsidiary"), "Subsidiary")
            
            normalized_subs.append({
                "name": group.normalized_name,
                "legal_name": group.normalized_name,
                "country": country,
                "ownership": ownership,
                "parent": legal_name,
                "relationship_type": rel_type,
                "registration_number": reg_num,
                "confidence": 0.0,
                "evidences": evidences,
                "notes": f"Normalized entity reconciled from variants: {', '.join(group.original_names)}."
            })
            
        # CRITICAL FIX: Retain all un-normalized candidate entities so zero items are dropped!
        for sub in subs:
            if sub["name"].strip().lower() not in processed_original_names:
                normalized_subs.append(sub)
                
        logs.append(f"Entity Normalization completed: consolidated/retained {len(normalized_subs)} clean corporate names (from {len(subs)} input items).")
        return {
            **state,
            "subsidiaries": normalized_subs,
            "logs": logs
        }
    except Exception as e:
        logger.error(f"Entity Normalization LLM query failed: {str(e)}")
        logs.append(f"Normalization consensus failed: {str(e)}. Defaulting to raw candidate list.")
        return state
