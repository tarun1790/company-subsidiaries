from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import List, Dict, Any
import time
import asyncio
import uuid
import os
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
from app.agents.coverage_estimator import coverage_estimator_agent
from app.agents.discovery_strategy_engine import discovery_strategy_engine_agent
from app.agents.relationship_classification import relationship_classification_agent
from app.agents.entity_verification import entity_verification_agent
from app.core.logging import logger

# Required minimum node output contracts
REQUIRED_OUTPUTS = {
    "sec_filings": ["sec_results"],
    "document_discovery": ["discovered_documents"],
    "document_intelligence": ["document_chunks"],
    "structured_entity_extraction": ["raw_claims"],
    "evidence_fusion": ["evidence_records", "candidate_entities"],
    "entity_normalization": ["normalized_entities"],
    "relationship_classification": ["relationships"],
    "entity_verification": ["verification_results"],
    "confidence_scoring": ["subsidiaries"],
    "knowledge_graph_builder": ["knowledge_graph"],
    "report_agent": ["pdf_path", "excel_path"],
}

def log_stage_counts(stage_name: str, state: dict) -> None:
    """Logs count telemetry for canonical state keys at node entry and exit."""
    logger.info(
        "[Stage Counts] %s | source_documents=%d document_chunks=%d raw_claims=%d "
        "candidate_entities=%d normalized_entities=%d relationships=%d evidence_records=%d "
        "verified_entities=%d warnings=%d errors=%d",
        stage_name,
        len(state.get("source_documents", [])),
        len(state.get("document_chunks", [])),
        len(state.get("raw_claims", [])),
        len(state.get("candidate_entities", []) or state.get("subsidiaries", [])),
        len(state.get("normalized_entities", [])),
        len(state.get("relationships", [])),
        len(state.get("evidence_records", [])),
        len(state.get("verification_results", [])),
        len(state.get("warnings", [])),
        len(state.get("errors", [])),
    )

def validate_node_outputs(stage_name: str, state: dict, strict: bool = False) -> None:
    """Lightweight invariant validation gate after every node execution."""
    required_keys = REQUIRED_OUTPUTS.get(stage_name, [])
    strict_env = os.environ.get("STRICT_PIPELINE_VALIDATION", "false").lower() == "true"
    is_strict = strict or strict_env

    for key in required_keys:
        value = state.get(key)
        if not value:
            msg = f"[{stage_name}] Contract Check: produced no required output key '{key}'"
            if is_strict:
                logger.error(f"STRICT GATE FAILURE: {msg}")
                raise RuntimeError(msg)
            else:
                logger.warning(f"CONTRACT WARNING: {msg}")
                state.setdefault("warnings", []).append({
                    "stage": stage_name,
                    "code": f"{stage_name.upper()}_EMPTY_{key.upper()}",
                    "message": msg,
                })

def resilient_agent_node(node_name: str, timeout: float = 30.0):
    """Decorator to enforce individual node contracts, telemetry logging, and error handling."""
    def decorator(func):
        from functools import wraps
        
        def get_metrics_summary(s: dict) -> str:
            parts = []
            if "query" in s:
                parts.append(f"query: '{s['query']}'")
            if "company_info" in s and isinstance(s["company_info"], dict) and s["company_info"]:
                parts.append(f"company_info: '{s['company_info'].get('legal_name')}'")
            
            for key in ["subsidiaries", "sec_results", "website_results", "registry_results", 
                        "search_results", "domain_results", "discovered_documents", 
                        "extracted_document_results", "pending_targets", "explored_entities", "errors"]:
                if key in s and s[key] is not None:
                    if isinstance(s[key], list):
                        parts.append(f"{key}: {len(s[key])}")
                        
            for key in ["document_contents", "knowledge_graph"]:
                if key in s and s[key] is not None:
                    if isinstance(s[key], dict):
                        parts.append(f"{key}: {len(s[key])}")
            return ", ".join(parts)

        @wraps(func)
        async def wrapper(state: AgentState) -> AgentState:
            # 1. Telemetry Entry
            log_stage_counts(f"{node_name}:entry", state)
            
            input_summary = get_metrics_summary(state)
            logger.info(f"[{node_name}] [INPUT] {input_summary}")
            
            start_time = time.time()
            try:
                # Execute node logic
                res = await func(state)
                duration = time.time() - start_time
                duration_msg = f"[Node Completed] Node '{node_name}' finished in {duration:.2f} seconds."
                logger.info(duration_msg)
                
                if not isinstance(res, dict):
                    res = {}
                
                full_next_state = {**state, **res}
                
                # 2. Invariant Contract Gate
                validate_node_outputs(node_name, full_next_state, strict=False)
                
                # 3. Telemetry Exit
                log_stage_counts(f"{node_name}:exit", full_next_state)
                output_summary = get_metrics_summary(full_next_state)
                logger.info(f"[{node_name}] [OUTPUT] {output_summary}")
                
                # Append log message
                if "logs" not in res:
                    res["logs"] = []
                res["logs"].append(duration_msg)
                return res
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
    workflow = StateGraph(AgentState)

    workflow.add_node("entity_resolution", resilient_agent_node("entity_resolution")(entity_resolution_agent))
    workflow.add_node("sec_filings", resilient_agent_node("sec_filings")(sec_filings_agent))
    workflow.add_node("official_website", resilient_agent_node("official_website")(official_website_agent))
    workflow.add_node("public_registry", resilient_agent_node("public_registry")(public_registry_agent))
    workflow.add_node("web_research", resilient_agent_node("web_research")(web_research_agent))
    workflow.add_node("domain_intelligence", resilient_agent_node("domain_intelligence")(domain_intelligence_agent))
    
    workflow.add_node("document_discovery", resilient_agent_node("document_discovery")(document_discovery_agent))
    workflow.add_node("document_intelligence", resilient_agent_node("document_intelligence")(document_intelligence_agent))
    workflow.add_node("structured_entity_extraction", resilient_agent_node("structured_entity_extraction")(structured_entity_extraction_agent))
    
    workflow.add_node("evidence_fusion", resilient_agent_node("evidence_fusion")(evidence_fusion_agent))
    workflow.add_node("entity_normalization", resilient_agent_node("entity_normalization")(entity_normalization_agent))
    workflow.add_node("relationship_classification", resilient_agent_node("relationship_classification")(relationship_classification_agent))
    workflow.add_node("entity_verification", resilient_agent_node("entity_verification")(entity_verification_agent))
    workflow.add_node("conflict_resolution", resilient_agent_node("conflict_resolution")(conflict_resolution_agent))
    workflow.add_node("relationship_verification", resilient_agent_node("relationship_verification")(relationship_verification_agent))
    workflow.add_node("confidence_scoring", resilient_agent_node("confidence_scoring")(confidence_scoring_agent))
    workflow.add_node("knowledge_graph_builder", resilient_agent_node("knowledge_graph_builder")(knowledge_graph_builder_agent))
    workflow.add_node("corporate_hierarchy", resilient_agent_node("corporate_hierarchy")(corporate_hierarchy_agent))
    workflow.add_node("report_agent", resilient_agent_node("report_agent")(report_agent))
    workflow.add_node("coverage_estimator", resilient_agent_node("coverage_estimator")(coverage_estimator_agent))
    workflow.add_node("discovery_strategy_engine", resilient_agent_node("discovery_strategy_engine")(discovery_strategy_engine_agent))
    workflow.add_node("loop_coordinator", resilient_agent_node("loop_coordinator")(loop_coordinator_agent))
    workflow.add_node("next_target_preparer", resilient_agent_node("next_target_preparer")(next_target_preparer_agent))

    workflow.set_entry_point("entity_resolution")
    
    def decide_flow(state: AgentState) -> List[str]:
        comp_info = state.get("company_info", {})
        if comp_info.get("status") == "failed":
            return [END]
        return ["sec_filings", "official_website", "public_registry", "web_research", "domain_intelligence"]

    workflow.add_conditional_edges("entity_resolution", decide_flow)
    
    workflow.add_edge("sec_filings", "document_discovery")
    workflow.add_edge("official_website", "document_discovery")
    workflow.add_edge("public_registry", "document_discovery")
    workflow.add_edge("web_research", "document_discovery")
    workflow.add_edge("domain_intelligence", "document_discovery")
    
    workflow.add_edge("document_discovery", "document_intelligence")
    workflow.add_edge("document_intelligence", "structured_entity_extraction")
    
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
    
    workflow.add_conditional_edges("loop_coordinator", route_discovery_loop)
    workflow.add_edge("next_target_preparer", "entity_resolution")

    return workflow.compile(checkpointer=MemorySaver())

async def execute_pipeline(initial_state: AgentState) -> AgentState:
    """Executes the compiled multi-agent state graph pipeline."""
    graph = build_workflow()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    logger.info(f"Initiating corporate subsidiary intelligence pipeline for query: {initial_state.get('query')} | Thread ID: {thread_id}")
    
    # Initialize canonical keys if missing
    initial_state.setdefault("source_documents", [])
    initial_state.setdefault("document_chunks", [])
    initial_state.setdefault("classified_documents", [])
    initial_state.setdefault("raw_claims", [])
    initial_state.setdefault("candidate_entities", [])
    initial_state.setdefault("normalized_entities", [])
    initial_state.setdefault("fused_claims", [])
    initial_state.setdefault("evidence_records", [])
    initial_state.setdefault("relationships", [])
    initial_state.setdefault("verification_results", [])
    initial_state.setdefault("warnings", [])
    initial_state.setdefault("errors", [])

    final_state = await graph.ainvoke(initial_state, config)
    return final_state
