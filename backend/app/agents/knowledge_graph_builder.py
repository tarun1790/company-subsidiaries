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
        "type": "Parent Company",
        "country": company_info.get("hq_country") or "Global",
        "confidence": 1.0,
        "evidences": []
    })
    
    # Add original query input node if it is different from resolved canonical parent
    original_query = company_info.get("original_query")
    if original_query and original_query.lower().strip() != legal_name.lower().strip():
        orig_id = re.sub(r"[^\w]", "", original_query.lower().strip())
        orig_classification = company_info.get("entity_classification") or "Query Input"
        
        kg_nodes.append({
            "id": orig_id,
            "label": original_query,
            "type": orig_classification,
            "country": company_info.get("hq_country") or "Global",
            "confidence": company_info.get("confidence") or 1.0,
            "evidences": [{"source_type": "User Search Input", "source_url": "", "extracted_text": f"Original query input classified as {orig_classification}"}]
        })
        
        kg_edges.append({
            "source": parent_id,
            "target": orig_id,
            "relationship": f"{orig_classification} of",
            "ownership": "100%",
            "confidence": company_info.get("confidence") or 1.0,
            "evidences": [{"source_type": "User Search Input", "source_url": "", "extracted_text": f"Resolved relationship to canonical parent: {legal_name}"}]
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
                "legal_name": sub.get("legal_name") or sub["name"],
                "relationship_type": sub.get("relationship_type") or "Subsidiary",
                "type": sub.get("relationship_type") or "Subsidiary",
                "confidence": sub["confidence"],
                "verification_status": sub.get("verification_status") or "Unverified",
                "evidences": sub.get("evidences") or [],
                "evidence_count": len(sub.get("evidences") or []),
                "parent": sub.get("parent") or legal_name,
                "country": sub.get("country") or "Global",
                "registry_id": sub.get("registration_number") or "N/A"
            })
        
        kg_edges.append({
            "source": parent_id,
            "target": sub_id,
            "relationship": sub.get("relationship_type") or "Subsidiary",
            "ownership": sub.get("ownership") or "100%",
            "confidence": sub["confidence"],
            "evidences": sub.get("evidences") or []
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
