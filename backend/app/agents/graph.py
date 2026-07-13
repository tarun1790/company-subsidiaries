from langgraph.graph import StateGraph, END
from typing import List
from app.agents.state import AgentState
from app.agents.entity_resolution import entity_resolution_agent
from app.agents.sec_filings import sec_filings_agent
from app.agents.official_website import official_website_agent
from app.agents.public_registry import public_registry_agent
from app.agents.web_research import web_research_agent
from app.agents.domain_intelligence import domain_intelligence_agent
from app.agents.document_discovery import document_discovery_agent
from app.agents.document_intelligence import document_intelligence_agent
from app.agents.structured_entity_extraction import structured_entity_extraction_agent
from app.agents.evidence_fusion import evidence_fusion_agent
from app.agents.entity_normalization import entity_normalization_agent
from app.agents.conflict_resolution import conflict_resolution_agent
from app.agents.relationship_verification import relationship_verification_agent
from app.agents.confidence_scoring import confidence_scoring_agent
from app.agents.knowledge_graph_builder import knowledge_graph_builder_agent
from app.agents.corporate_hierarchy import corporate_hierarchy_agent
from app.agents.report_agent import report_agent
from app.agents.evaluation_benchmark import evaluation_benchmark_agent
from app.core.logging import logger

def build_workflow():
    # Initialize StateGraph with our state schema
    workflow = StateGraph(AgentState)

    # Add all agent nodes
    workflow.add_node("entity_resolution", entity_resolution_agent)
    workflow.add_node("sec_filings", sec_filings_agent)
    workflow.add_node("official_website", official_website_agent)
    workflow.add_node("public_registry", public_registry_agent)
    workflow.add_node("web_research", web_research_agent)
    workflow.add_node("domain_intelligence", domain_intelligence_agent)
    
    # Split document pipeline nodes
    workflow.add_node("document_discovery", document_discovery_agent)
    workflow.add_node("document_intelligence", document_intelligence_agent)
    workflow.add_node("structured_entity_extraction", structured_entity_extraction_agent)
    
    workflow.add_node("evidence_fusion", evidence_fusion_agent)
    workflow.add_node("entity_normalization", entity_normalization_agent)
    workflow.add_node("conflict_resolution", conflict_resolution_agent)
    workflow.add_node("relationship_verification", relationship_verification_agent)
    workflow.add_node("confidence_scoring", confidence_scoring_agent)
    workflow.add_node("knowledge_graph_builder", knowledge_graph_builder_agent)
    workflow.add_node("corporate_hierarchy", corporate_hierarchy_agent)
    workflow.add_node("report_agent", report_agent)
    workflow.add_node("evaluation_benchmark", evaluation_benchmark_agent)

    # Set flow sequence
    workflow.set_entry_point("entity_resolution")
    
    def decide_flow(state: AgentState) -> List[str]:
        comp_info = state.get("company_info", {})
        if comp_info.get("status") == "failed":
            return [END]
        return ["sec_filings", "official_website", "public_registry", "web_research", "domain_intelligence"]

    workflow.add_conditional_edges(
        "entity_resolution",
        decide_flow
    )
    
    # Fan-in parallel collection pipelines to document_discovery
    workflow.add_edge("sec_filings", "document_discovery")
    workflow.add_edge("official_website", "document_discovery")
    workflow.add_edge("public_registry", "document_discovery")
    workflow.add_edge("web_research", "document_discovery")
    workflow.add_edge("domain_intelligence", "document_discovery")
    
    # Sequential Document Pipeline flow
    workflow.add_edge("document_discovery", "document_intelligence")
    workflow.add_edge("document_intelligence", "structured_entity_extraction")
    
    # Sequential Consolidation Pipeline flow
    workflow.add_edge("structured_entity_extraction", "evidence_fusion")
    workflow.add_edge("evidence_fusion", "entity_normalization")
    workflow.add_edge("entity_normalization", "conflict_resolution")
    workflow.add_edge("conflict_resolution", "relationship_verification")
    workflow.add_edge("relationship_verification", "confidence_scoring")
    workflow.add_edge("confidence_scoring", "knowledge_graph_builder")
    workflow.add_edge("knowledge_graph_builder", "corporate_hierarchy")
    workflow.add_edge("corporate_hierarchy", "report_agent")
    workflow.add_edge("report_agent", "evaluation_benchmark")
    workflow.add_edge("evaluation_benchmark", END)

    # Compile the graph
    return workflow.compile()

# Instantiated compiled workflow
pipeline_graph = build_workflow()

async def execute_pipeline(query: str, update_hook=None) -> AgentState:
    """Executes the corporate research multi-agent pipeline and triggers hooks for progress monitoring."""
    # Initial state structure
    initial_state: AgentState = {
        "query": query,
        "company_info": {},
        "subsidiaries": [],
        "logs": [],
        "pdf_path": None,
        "excel_path": None,
        "csv_path": None,
        "json_path": None,
        "errors": []
    }
    
    logger.info(f"Initiating corporate subsidiary intelligence pipeline for query: {query}")
    
    current_state = initial_state
    
    # We execute node by node so we can stream progress and logs back to API websockets or clients
    async for event in pipeline_graph.astream(initial_state):
        # Event is a dictionary matching node_name -> state update
        for node_name, state_update in event.items():
            logger.info(f"Node completed: {node_name}")
            
            # Combine current state logs and errors
            current_state.update(state_update)
            
            # Call hook if defined to stream status
            if update_hook:
                try:
                    last_log = current_state["logs"][-1] if current_state["logs"] else f"Completed stage {node_name}."
                    await update_hook(node_name, last_log, current_state)
                except Exception as hook_err:
                    logger.error(f"Error executing progress update hook: {str(hook_err)}")
                    
    return current_state
