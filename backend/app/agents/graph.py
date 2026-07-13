from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.entity_resolution import entity_resolution_agent
from app.agents.sec_filings import sec_filings_agent
from app.agents.official_website import official_website_agent
from app.agents.public_registry import public_registry_agent
from app.agents.web_research import web_research_agent
from app.agents.doc_extraction import doc_extraction_agent
from app.agents.verification import verification_agent
from app.agents.corporate_hierarchy import corporate_hierarchy_agent
from app.agents.report_agent import report_agent
from app.core.logging import logger

def build_workflow():
    # Initialize StateGraph with our state schema
    workflow = StateGraph(AgentState)

    # Add all 9 agent nodes
    workflow.add_node("entity_resolution", entity_resolution_agent)
    workflow.add_node("sec_filings", sec_filings_agent)
    workflow.add_node("official_website", official_website_agent)
    workflow.add_node("public_registry", public_registry_agent)
    workflow.add_node("web_research", web_research_agent)
    workflow.add_node("doc_extraction", doc_extraction_agent)
    workflow.add_node("verification", verification_agent)
    workflow.add_node("corporate_hierarchy", corporate_hierarchy_agent)
    workflow.add_node("report_agent", report_agent)

    # Set flow sequence
    workflow.set_entry_point("entity_resolution")
    
    def decide_flow(state: AgentState) -> str:
        comp_info = state.get("company_info", {})
        if comp_info.get("status") == "failed":
            return "end"
        return "continue"

    workflow.add_conditional_edges(
        "entity_resolution",
        decide_flow,
        {
            "continue": "sec_filings",
            "end": END
        }
    )
    workflow.add_edge("sec_filings", "official_website")
    workflow.add_edge("official_website", "public_registry")
    workflow.add_edge("public_registry", "web_research")
    workflow.add_edge("web_research", "doc_extraction")
    workflow.add_edge("doc_extraction", "verification")
    workflow.add_edge("verification", "corporate_hierarchy")
    workflow.add_edge("corporate_hierarchy", "report_agent")
    workflow.add_edge("report_agent", END)

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
