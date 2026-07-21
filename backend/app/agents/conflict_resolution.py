from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.agents.state import AgentState
from app.agents.llm import get_llm
from app.core.logging import logger
from langchain_core.prompts import ChatPromptTemplate

class ConflictItem(BaseModel):
    name: str = Field(description="Name of the candidate entity.")
    has_conflict: bool = Field(description="True if there is a contradiction in ownership, registry facts, or sale status between sources.")
    resolved_value: Optional[str] = Field(None, description="The resolved relationship/ownership context after auditing sources.")
    explanation: str = Field(description="Explain why the contradiction is resolved, or if it remains a conflict.")

class ConflictResolutionOutput(BaseModel):
    resolutions: List[ConflictItem] = Field(default=[], description="Conflict resolutions list.")

async def conflict_resolution_agent(state: AgentState) -> AgentState:
    """Agent 14: Inspects candidate entities for conflicting facts (e.g., sold vs owned) and reconciles them."""
    subs = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    legal_name = state["company_info"].get("legal_name") or state["query"]
    
    if not subs:
        return state
        
    logs.append(f"Running Fast Conflict Resolution Agent over {len(subs)} entities...")
    logger.info("Executing conflict resolution checks...")

    # Fast-Path: Identify only entities with multi-source evidence containing potential contradiction terms
    conflict_candidates = []
    conflict_keywords = {"sold", "divested", "former", "dissolved", "acquired", "merged", "inactive", "struck off"}
    
    for s in subs:
        evidences = s.get("evidences", [])
        combined_text = " ".join([ev.get("extracted_text", "").lower() for ev in evidences])
        if len(evidences) > 1 and any(kw in combined_text for kw in conflict_keywords):
            conflict_candidates.append(s)

    if not conflict_candidates:
        logs.append("No active evidence conflicts detected across candidate entities.")
        return state

    logs.append(f"Found {len(conflict_candidates)} potential conflict candidates for deep AI auditing...")
    
    candidates_context = []
    for s in conflict_candidates:
        ev_texts = [f"[{ev['source_type']}]: {ev.get('extracted_text', 'Verified')}" for ev in s.get("evidences", [])]
        candidates_context.append(
            f"Entity: {s['name']}\n"
            f"Reported Country: {s.get('country')}\n"
            f"Reported Ownership: {s.get('ownership')}\n"
            f"Claims:\n" + "\n".join(ev_texts)
        )

    try:
        llm = get_llm(capability="reasoning")
        structured_llm = llm.with_structured_output(ConflictResolutionOutput)
        
        system_prompt = (
            "You are an expert Evidence Conflict Resolution Agent.\n"
            "Your task is to identify contradiction conflicts (e.g. one source says owned, another says sold).\n"
            "If resolved, state why; if contradictory, flag has_conflict = True."
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Ultimate Parent: {parent}\n\nCandidate Entities Auditing:\n{context}")
        ])
        
        chain = prompt | structured_llm
        result = await chain.ainvoke({
            "parent": legal_name,
            "context": "\n---\n".join(candidates_context)
        })
        
        res_map = {r.name.lower().strip(): r for r in result.resolutions}
        
        updated_subs = []
        for s in subs:
            s_key = s["name"].lower().strip()
            if s_key in res_map:
                res_item = res_map[s_key]
                if res_item.has_conflict:
                    s["is_conflicting"] = True
                    s["notes"] = (s.get("notes", "") + f" Conflict: {res_item.explanation}").strip()
                elif res_item.resolved_value:
                    s["notes"] = (s.get("notes", "") + f" Resolved: {res_item.explanation}").strip()
            updated_subs.append(s)
            
        return {**state, "subsidiaries": updated_subs, "logs": logs}
        
    except Exception as e:
        logger.warning(f"Fast conflict resolution AI warning: {str(e)}")
        return state
