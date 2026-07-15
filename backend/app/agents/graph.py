from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import List, Dict, Any
import time
import asyncio
import uuid
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
from app.agents.loop_coordinator import loop_coordinator_agent, next_target_preparer_agent, route_discovery_loop
from app.agents.discovery_intelligence import coverage_estimator_agent, discovery_strategy_engine_agent, relationship_classification_agent, entity_verification_agent
from app.core.logging import logger

def resilient_agent_node(node_name: str, timeout: float = 30.0):
    """Decorator to enforce individual timeouts, handle errors gracefully, and log step latency."""
    def decorator(func):
        from functools import wraps
        @wraps(func)
        async def wrapper(state: AgentState) -> AgentState:
            logger.info(f"Initiating node '{node_name}'...")
            start_time = time.time()
            try:
                # Execute node with timeout
                res = await asyncio.wait_for(func(state), timeout=timeout)
                duration = time.time() - start_time
                duration_msg = f"[Node Completed] Node '{node_name}' finished in {duration:.2f} seconds."
                logger.info(duration_msg)
                
                # Make sure result is a dict
                if not isinstance(res, dict):
                    res = {}
                
                # Append log message
                if "logs" not in res:
                    res["logs"] = []
                res["logs"].append(duration_msg)
                return res
            except asyncio.TimeoutError:
                duration = time.time() - start_time
                timeout_msg = f"[Node Timeout] Node '{node_name}' timed out after {timeout}s (total: {duration:.2f}s). Continuing with partial results."
                logger.warning(timeout_msg)
                return {
                    "logs": [timeout_msg],
                    "errors": [f"Node '{node_name}' timed out."]
                }
            except Exception as e:
                duration = time.time() - start_time
                error_msg = f"[Node Error] Node '{node_name}' failed after {duration:.2f}s: {str(e)}"
                logger.error(error_msg)
                return {
                    "logs": [error_msg],
                    "errors": [error_msg]
                }
        return wrapper
    return decorator

def build_workflow():
    # Initialize StateGraph with our state schema
    workflow = StateGraph(AgentState)

    # Add all agent nodes with timeouts
    workflow.add_node("entity_resolution", resilient_agent_node("entity_resolution", timeout=60.0)(entity_resolution_agent))
    workflow.add_node("sec_filings", resilient_agent_node("sec_filings", timeout=20.0)(sec_filings_agent))
    workflow.add_node("official_website", resilient_agent_node("official_website", timeout=30.0)(official_website_agent))
    workflow.add_node("public_registry", resilient_agent_node("public_registry", timeout=20.0)(public_registry_agent))
    workflow.add_node("web_research", resilient_agent_node("web_research", timeout=20.0)(web_research_agent))
    workflow.add_node("domain_intelligence", resilient_agent_node("domain_intelligence", timeout=15.0)(domain_intelligence_agent))
    
    # Split document pipeline nodes
    workflow.add_node("document_discovery", resilient_agent_node("document_discovery", timeout=20.0)(document_discovery_agent))
    workflow.add_node("document_intelligence", resilient_agent_node("document_intelligence", timeout=30.0)(document_intelligence_agent))
    workflow.add_node("structured_entity_extraction", resilient_agent_node("structured_entity_extraction", timeout=20.0)(structured_entity_extraction_agent))
    
    workflow.add_node("evidence_fusion", resilient_agent_node("evidence_fusion", timeout=20.0)(evidence_fusion_agent))
    workflow.add_node("entity_normalization", resilient_agent_node("entity_normalization", timeout=30.0)(entity_normalization_agent))
    workflow.add_node("relationship_classification", resilient_agent_node("relationship_classification", timeout=20.0)(relationship_classification_agent))
    workflow.add_node("entity_verification", resilient_agent_node("entity_verification", timeout=20.0)(entity_verification_agent))
    workflow.add_node("conflict_resolution", resilient_agent_node("conflict_resolution", timeout=30.0)(conflict_resolution_agent))
    workflow.add_node("relationship_verification", resilient_agent_node("relationship_verification", timeout=30.0)(relationship_verification_agent))
    workflow.add_node("confidence_scoring", resilient_agent_node("confidence_scoring", timeout=20.0)(confidence_scoring_agent))
    workflow.add_node("knowledge_graph_builder", resilient_agent_node("knowledge_graph_builder", timeout=20.0)(knowledge_graph_builder_agent))
    workflow.add_node("corporate_hierarchy", resilient_agent_node("corporate_hierarchy", timeout=30.0)(corporate_hierarchy_agent))
    workflow.add_node("report_agent", resilient_agent_node("report_agent", timeout=20.0)(report_agent))
    workflow.add_node("coverage_estimator", resilient_agent_node("coverage_estimator", timeout=20.0)(coverage_estimator_agent))
    workflow.add_node("discovery_strategy_engine", resilient_agent_node("discovery_strategy_engine", timeout=20.0)(discovery_strategy_engine_agent))
    workflow.add_node("loop_coordinator", resilient_agent_node("loop_coordinator", timeout=20.0)(loop_coordinator_agent))
    workflow.add_node("next_target_preparer", resilient_agent_node("next_target_preparer", timeout=15.0)(next_target_preparer_agent))

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
    workflow.add_edge("entity_normalization", "relationship_classification")
    workflow.add_edge("relationship_classification", "entity_verification")
    workflow.add_edge("entity_verification", "conflict_resolution")
    workflow.add_edge("conflict_resolution", "relationship_verification")
    workflow.add_edge("relationship_verification", "confidence_scoring")
    workflow.add_edge("confidence_scoring", "knowledge_graph_builder")
    workflow.add_edge("knowledge_graph_builder", "corporate_hierarchy")
    workflow.add_edge("corporate_hierarchy", "report_agent")
    workflow.add_edge("report_agent", "coverage_estimator")
    workflow.add_edge("coverage_estimator", "discovery_strategy_engine")
    workflow.add_edge("discovery_strategy_engine", "loop_coordinator")
    
    workflow.add_conditional_edges(
        "loop_coordinator",
        route_discovery_loop
    )
    workflow.add_edge("next_target_preparer", "entity_resolution")

    # Compile the graph with MemorySaver checkpointer
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)

# Instantiated compiled workflow
pipeline_graph = build_workflow()

async def execute_pipeline(query: str, update_hook=None, thread_id: str = None) -> AgentState:
    """Executes the corporate research multi-agent pipeline and triggers hooks for progress monitoring."""
    # Initial state structure
    initial_state: AgentState = {
        "query": query,
        "company_info": {},
        "subsidiaries": [],
        "sec_results": [],
        "website_results": [],
        "registry_results": [],
        "search_results": [],
        "domain_results": [],
        "extracted_document_results": [],
        "logs": [],
        "discovered_documents": [],
        "document_contents": {},
        "knowledge_graph": {"nodes": [], "edges": []},
        "pdf_path": None,
        "excel_path": None,
        "csv_path": None,
        "json_path": None,
        "errors": [],
        "current_iteration": 1,
        "explored_entities": [query],
        "pending_targets": [],
        "coverage_score": {"overall": 0.0},
        "evidence_cache": {},
        "source_statistics": {},
        "execution_summary": {"iterations_run": 0, "successful_strategies": [], "sources_with_data": [], "unseen_entities_count": 0}
    }
    
    if not thread_id:
        thread_id = str(uuid.uuid4())
        
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 100
    }
    logger.info(f"Initiating corporate subsidiary intelligence pipeline for query: {query} | Thread ID: {thread_id}")
    
    current_state = initial_state
    
    # We execute node by node so we can stream progress and logs back to API websockets or clients
    async for event in pipeline_graph.astream(initial_state, config):
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
