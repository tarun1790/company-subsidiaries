import re
from app.agents.state import AgentState
from app.core.logging import logger

async def knowledge_graph_builder_agent(state: AgentState) -> AgentState:
    """Agent 13: Constructs formal entity nodes and directed edges for Knowledge Graph output."""
    subs = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    legal_name = state["company_info"].get("legal_name") or state["query"]
    company_info = state["company_info"]
    
    logs.append("Running Knowledge Graph Builder Agent...")
    logger.info("Executing Knowledge Graph Builder Agent.")
    
    kg_nodes = []
    kg_edges = []
    
    # 1. Base Parent Node
    parent_id = re.sub(r"[^\w]", "", legal_name.lower().strip())
    kg_nodes.append({
        "id": parent_id,
        "label": legal_name,
        "type": "Parent",
        "country": company_info.get("hq_country") or "Global",
        "confidence": 1.0,
        "evidences": []
    })
    
    # 2. Populate Nodes and Directed Edges
    for sub in subs:
        sub_id = re.sub(r"[^\w]", "", sub["name"].lower().strip())
        
        # Add entity node details
        kg_nodes.append({
            "id": sub_id,
            "label": sub["name"],
            "type": sub["relationship_type"],
            "country": sub["country"],
            "confidence": sub["confidence"],
            "evidences": sub["evidences"]
        })
        
        # Add directed ownership edge details
        kg_edges.append({
            "source": parent_id,
            "target": sub_id,
            "relationship": sub["relationship_type"],
            "ownership": sub["ownership"],
            "confidence": sub["confidence"],
            "evidences": sub["evidences"]
        })
        
    knowledge_graph = {
        "nodes": kg_nodes,
        "edges": kg_edges
    }
    
    logs.append(f"Knowledge Graph created with {len(kg_nodes)} nodes and {len(kg_edges)} edges.")
    return {
        **state,
        "knowledge_graph": knowledge_graph,
        "logs": logs
    }
