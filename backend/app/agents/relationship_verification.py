from pydantic import BaseModel, Field
from typing import List, Optional
from app.agents.state import AgentState
from app.agents.llm import get_llm
from app.core.logging import logger
from langchain_core.prompts import ChatPromptTemplate

class VerifiedRelationship(BaseModel):
    name: str = Field(description="Name of the candidate entity.")
    relationship_confirmed: bool = Field(description="True if the evidence confirms it is a valid subsidiary/brand/acquisition/division of parent.")
    inferred_relationship_type: str = Field(description="Classification: Subsidiary, Brand, Acquisition, Division.")
    explanation: str = Field(description="Short sentence explaining the relationship evidence.")

class VerificationOutput(BaseModel):
    verifications: List[VerifiedRelationship] = Field(default=[], description="Relationships verified.")

async def relationship_verification_agent(state: AgentState) -> AgentState:
    """Agent 11: Validates parent-child relationships using evidence context."""
    subs = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    legal_name = state["company_info"].get("legal_name") or state["query"]
    
    if not subs:
        return state
        
    logs.append("Running Relationship Verification Agent...")
    logger.info("Executing relationship verification model...")
    
    # Format candidates list with their grouped evidence quotes
    candidates_context = []
    for s in subs:
        evidence_snippets = []
        for ev in s.get("evidences", []):
            evidence_snippets.append(f"[{ev['source_type']}]: {ev.get('extracted_text', 'Verified')}")
        candidates_context.append(
            f"Entity: {s['name']}\n"
            f"Claims context:\n" + "\n".join(evidence_snippets)
        )
        
    llm = get_llm(capability="verification")
    structured_llm = llm.with_structured_output(VerificationOutput)
    
    system_prompt = (
        "You are an expert Relationship Verification Agent.\n"
        "Your task is to analyze candidate entities and verify if the provided claims context confirms "
        "their relationship to the parent company.\n"
        "RULES:\n"
        "1. Confirm only if the evidence directly indicates ownership, acquisition, or brand alignment.\n"
        "2. Set relationship_confirmed to False if the evidence is missing, unverified, or unrelated."
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Ultimate Parent: {parent}\n\nCandidate Relationships to Verify:\n{context}")
    ])
    
    verified_subs = []
    try:
        chain = prompt | structured_llm
        result = await chain.ainvoke({
            "parent": legal_name,
            "context": "\n\n".join(candidates_context)[:25000] # Safe limit
        })
        
        processed_names = set()
        for ver in result.verifications:
            matching_sub = next((s for s in subs if s["name"].lower().strip() == ver.name.lower().strip() or s["name"].lower().strip() in ver.name.lower().strip()), None)
            if matching_sub:
                processed_names.add(matching_sub["name"].lower().strip())
                if ver.relationship_confirmed:
                    matching_sub["verification_status"] = "Verified"
                    if ver.inferred_relationship_type:
                        matching_sub["relationship_type"] = ver.inferred_relationship_type
                    matching_sub["notes"] = ver.explanation
                else:
                    matching_sub["verification_status"] = "Unverified"
                    matching_sub["notes"] = f"Unconfirmed relationship: {ver.explanation}"
                verified_subs.append(matching_sub)
                
        # Retain all remaining subsidiaries as Unverified so zero data is dropped!
        for s in subs:
            if s["name"].lower().strip() not in processed_names:
                s["verification_status"] = "Unverified"
                verified_subs.append(s)
                
        logs.append(f"Relationship Verification complete: evaluated {len(verified_subs)} entities ({len([v for v in verified_subs if v.get('verification_status') == 'Verified'])} verified).")
        return {
            **state,
            "subsidiaries": verified_subs,
            "logs": logs
        }
    except Exception as e:
        logger.error(f"Relationship Verification Agent query failed: {str(e)}")
        logs.append(f"Relationship verification error: {str(e)}. Defaulting to input list.")
        return state
