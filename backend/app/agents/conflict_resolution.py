from pydantic import BaseModel, Field
from typing import List, Optional
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
        
    logs.append("Running Evidence Conflict Resolution Agent...")
    logger.info("Executing conflict resolution checks.")
    
    # Format candidates context list with evidence source texts
    candidates_context = []
    for s in subs:
        ev_texts = [f"[{ev['source_type']}]: {ev.get('extracted_text', 'Verified')}" for ev in s.get("evidences", [])]
        candidates_context.append(
            f"Entity: {s['name']}\n"
            f"Reported Country: {s.get('country')}\n"
            f"Reported Ownership: {s.get('ownership')}\n"
            f"Claims:\n" + "\n".join(ev_texts)
        )
        
    llm = get_llm()
    structured_llm = llm.with_structured_output(ConflictResolutionOutput)
    
    system_prompt = (
        "You are an expert Evidence Conflict Resolution Agent.\n"
        "Your task is to identify contradiction conflicts (e.g., one source says owned, another says sold; "
        "or competing parent claims like Google vs Alphabet).\n"
        "RULES:\n"
        "1. Reconcile parent hierarchy chains (e.g. Alphabet owns Google, Google owns DeepMind, so both Alphabet and Google own DeepMind indirectly. This is NOT a contradiction, resolve it to Alphabet/Google).\n"
        "2. If one source explicitly says 'sold' or 'divested' and is newer or authoritative (like a news report or press release after an annual report), mark the conflict resolved with the divested status, or flag as has_conflict = True if unresolved."
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Ultimate Parent: {parent}\n\nCandidate Entities Auditing:\n{context}")
    ])
    
    resolved_subs = []
    try:
        chain = prompt | structured_llm
        result = await chain.ainvoke({
            "parent": legal_name,
            "context": "\n\n".join(candidates_context)[:25000]
        })
        
        for res in result.resolutions:
            matching_sub = next((s for s in subs if s["name"].lower().strip() == res.name.lower().strip()), None)
            if matching_sub:
                matching_sub["conflict_detected"] = res.has_conflict
                if res.has_conflict:
                    matching_sub["notes"] = f"Warning: Contradictory evidence detected. {res.explanation}"
                else:
                    matching_sub["notes"] = res.explanation
                resolved_subs.append(matching_sub)
                
        # Keep any items not processed by LLM as-is
        processed_names = {res.name.lower().strip() for res in result.resolutions}
        for s in subs:
            if s["name"].lower().strip() not in processed_names:
                s["conflict_detected"] = False
                resolved_subs.append(s)
                
        logs.append(f"Evidence Conflict Resolution completed. Audited {len(resolved_subs)} entities.")
        return {
            **state,
            "subsidiaries": resolved_subs,
            "logs": logs
        }
    except Exception as e:
        logger.error(f"Conflict Resolution Agent query failed: {str(e)}")
        logs.append(f"Conflict resolution error: {str(e)}. Defaulting to input list.")
        return state
