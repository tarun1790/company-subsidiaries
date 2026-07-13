from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from app.agents.state import AgentState
from app.agents.llm import get_llm
from app.core.logging import logger
from langchain_core.prompts import ChatPromptTemplate

class HierarchyNode(BaseModel):
    name: str = Field(description="Name of the entity.")
    parent: str = Field(description="Direct parent company of this entity.")
    relationship_type: str = Field(description="Classification: Parent, Holding Company, Subsidiary, Division, Brand.")
    depth: int = Field(description="Hierarchy depth level (0 for ultimate parent, 1 for direct child, 2 for nested child).")

class HierarchyTree(BaseModel):
    nodes: List[HierarchyNode] = Field(default=[], description="Structured hierarchy nodes list.")

async def corporate_hierarchy_agent(state: AgentState) -> AgentState:
    """Agent 8: Analyzes verified subsidiaries, determines parent-child relationships, and structures the corporate tree."""
    subs = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    legal_name = state["company_info"].get("legal_name") or state["query"]
    
    logs.append("Building corporate hierarchy structure...")
    logger.info("Running Corporate Hierarchy Agent.")

    if not subs:
        logs.append("No verified subsidiaries to build hierarchy for.")
        return state

    # Build map of verified entities
    sub_names = [s["name"] for s in subs]
    
    # Run LLM to resolve hierarchical connections (some subsidiaries might belong under other subsidiaries)
    llm = get_llm()
    structured_llm = llm.with_structured_output(HierarchyTree)
    
    system_prompt = (
        "You are an expert systems architect for corporate structures.\n"
        "Your task is to structure the resolved corporate entities into a clean, multi-level hierarchy tree.\n"
        "The ultimate parent company is {parent}.\n"
        "Examine the list of entities and determine if any should be children of other entities in the list (depth 2) "
        "rather than direct children of the parent (depth 1).\n"
        "Classify each node: Parent (only for the ultimate parent), Holding Company, Subsidiary, Division, Brand.\n"
        "Return a structured list of nodes with name, direct parent, type, and depth level."
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Ultimate Parent: {parent}\n\nList of Entities to place:\n{entities}")
    ])
    
    try:
        entities_text = "\n".join([f"- Name: {s['name']}, Notes: {s.get('notes', '')}" for s in subs])
        chain = prompt | structured_llm
        result = await chain.ainvoke({
            "parent": legal_name,
            "entities": entities_text
        })
        
        # Merge hierarchy assignments back to subsidiaries state
        node_map = {n.name.lower().strip(): n for n in result.nodes}
        
        updated_subs = []
        for s in subs:
            s_name = s["name"]
            node = node_map.get(s_name.lower().strip())
            
            if node:
                # Update parent and relationship type based on hierarchy analysis
                s["parent"] = node.parent
                s["relationship_type"] = node.relationship_type
                # Add depth to metadata
                s["depth"] = node.depth
            else:
                # Fallback default
                s["parent"] = legal_name
                s["relationship_type"] = "Subsidiary"
                s["depth"] = 1
                
            updated_subs.append(s)

        logs.append("Hierarchy tree compiled successfully.")
        return {
            **state,
            "subsidiaries": updated_subs,
            "logs": logs
        }
    except Exception as e:
        logger.error(f"Error compiling corporate hierarchy tree: {str(e)}")
        logs.append(f"Failed to optimize hierarchy: {str(e)}. Defaulting to flat layout.")
        
        # Default flat layout fallback
        flat_subs = []
        for s in subs:
            s["parent"] = legal_name
            s["relationship_type"] = "Subsidiary"
            s["depth"] = 1
            flat_subs.append(s)
            
        return {
            **state,
            "subsidiaries": flat_subs,
            "logs": logs
        }
