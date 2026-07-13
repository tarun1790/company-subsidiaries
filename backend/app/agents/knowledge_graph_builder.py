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
        "type": company_info.get("entity_classification") or "Parent",
        "country": company_info.get("hq_country") or "Global",
        "confidence": 1.0,
        "evidences": []
    })
    
    # Add resolved corporate group entities as nodes and edges
    group_entities = company_info.get("metadata_fields", {}).get("corporate_group_entities") or []
    for ge in group_entities:
        ge_name = ge.get("legal_name")
        ge_type = ge.get("entity_type") or "Regional Operating Entity"
        ge_rel = ge.get("relationship") or "Operating Entity"
        
        ge_id = re.sub(r"[^\w]", "", ge_name.lower().strip())
        if ge_id != parent_id:
            kg_nodes.append({
                "id": ge_id,
                "label": ge_name,
                "type": ge_type,
                "country": company_info.get("hq_country") or "Global",
                "confidence": 1.0,
                "evidences": [{"source_type": "Entity Resolution Registry", "source_url": "", "extracted_text": f"Reconciled related entity: {ge_name} ({ge_type})"}]
            })
            
            kg_edges.append({
                "source": parent_id,
                "target": ge_id,
                "relationship": ge_rel,
                "ownership": "100%",
                "confidence": 1.0,
                "evidences": [{"source_type": "Entity Resolution Registry", "source_url": "", "extracted_text": f"Corporate Group relationship: {ge_name} ({ge_type})"}]
            })
    
    # 2. Populate Nodes and Directed Edges from subsidiaries list
    for sub in subs:
        sub_id = re.sub(r"[^\w]", "", sub["name"].lower().strip())
        
        # Check if node already added to avoid duplicate node keys
        if not any(node["id"] == sub_id for node in kg_nodes):
            kg_nodes.append({
                "id": sub_id,
                "label": sub["name"],
                "type": sub["relationship_type"],
                "country": sub["country"],
                "confidence": sub["confidence"],
                "evidences": sub["evidences"]
            })
        
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
