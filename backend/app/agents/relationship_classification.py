import re
import asyncio
from typing import Dict, List, Any
from pydantic import BaseModel, Field
from app.agents.state import AgentState
from app.agents.llm import get_llm
from langchain_core.prompts import ChatPromptTemplate
from app.core.logging import logger

class RelationshipCheck(BaseModel):
    is_subsidiary: bool = Field(description="Is this entity genuinely a subsidiary, brand, or joint venture of the parent company? (False if it is a competitor, news outlet, unrelated company, or sentence fragment)")
    relationship_type: str = Field(description="Direct Subsidiary, Holding Company, Brand, Joint Venture, Excluded, or Mentioned Entity")

async def verify_relationship_llm(parent: str, entity: str, evidences: List[Dict]) -> str:
    if not evidences:
        return "Direct Subsidiary" # fallback
    
    contexts = [ev.get("extracted_text") or str(ev) for ev in evidences[:3]]
    context_str = "\n".join(contexts)
    
    llm = get_llm(capability="classification")
    structured_llm = llm.with_structured_output(RelationshipCheck)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert corporate intelligence analyst. Analyze the relationship between the Parent Company and the Entity based ONLY on the provided context evidence. If the Entity is a competitor, a news publisher reporting on the parent, a generic technology/service provider, or a random sentence fragment, set is_subsidiary=False and relationship_type='Excluded'. Otherwise, classify its relationship type."),
        ("user", "Parent: {parent}\nEntity: {entity}\nContext:\n{context}")
    ])
    
    try:
        res = await (prompt | structured_llm).ainvoke({"parent": parent, "entity": entity, "context": context_str})
        if not res.is_subsidiary or res.relationship_type in ["Excluded", "Mentioned Entity"]:
            return "Excluded"
        return res.relationship_type
    except Exception as e:
        logger.warning(f"Relationship LLM failed for {entity}: {e}")
        return "Direct Subsidiary"

async def relationship_classification_agent(state: AgentState) -> AgentState:
    """Agent 10: Classifies verified candidate links using an LLM to drop competitors and non-subsidiaries."""
    logs = state.get("logs") or []
    warnings = state.get("warnings") or []
    subs = state.get("subsidiaries") or state.get("normalized_entities") or []
    legal_name = state.get("company_info", {}).get("legal_name") or state.get("query")
    
    logs.append("Running Relationship Classification Agent (LLM Verification)...")
    
    if not subs:
        return {"relationships": [], "logs": logs, "warnings": warnings}

    relationships = []
    classified_subs = []
    
    async def process_sub(s):
        name = s.get("name", "")
        ownership = str(s.get("ownership", "")).lower()
        evidences = s.get("evidences", [])
        
        if name.lower() == legal_name.lower() or s.get("relationship_type") == "Primary Entity":
            s["relationship_type"] = "Primary Entity"
            return s
            
        # If the source is SEC Exhibit 21, it's definitely a subsidiary
        is_sec = any("SEC" in str(ev.get("source_type", "")) for ev in evidences)
        
        if is_sec:
            if "holding" in name.lower() or "securit" in name.lower():
                rel_type = "Holding Company"
            else:
                rel_type = "Direct Subsidiary"
        else:
            rel_type = await verify_relationship_llm(legal_name, name, evidences)
            
        s["relationship_type"] = rel_type
        return s
        
    tasks = [process_sub(s) for s in subs]
    results = await asyncio.gather(*tasks)
    
    for s in results:
        rel_type = s.get("relationship_type", "Excluded")
        if rel_type == "Excluded":
            continue
            
        classified_subs.append(s)
        relationships.append({
            "source": s.get("parent") or legal_name,
            "target": s.get("name"),
            "relationship_type": rel_type,
            "ownership": s.get("ownership", "100%"),
            "confidence": s.get("confidence", 0.85)
        })

    logs.append(f"Relationship Classification produced {len(relationships)} valid verified relationship edges.")
    return {
        "subsidiaries": classified_subs,
        "relationships": relationships,
        "logs": logs,
        "warnings": warnings
    }
