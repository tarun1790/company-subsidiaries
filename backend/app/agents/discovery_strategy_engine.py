from typing import Dict, List, Any
from app.agents.state import AgentState
from app.core.logging import logger

async def discovery_strategy_engine_agent(state: AgentState) -> AgentState:
    """Agent 13: Identifies missing parent/child links and targets next collection strategies."""
    logs = state.get("logs") or []
    coverage = state.get("coverage_score") or {"overall": 0.0}
    summary = state.get("execution_summary") or {}
    company_info = state.get("company_info") or {}
    is_sec = company_info.get("is_sec_registered", False)
    
    logs.append("Running Adaptive Discovery Strategy Engine...")
    
    strategies = []
    if not is_sec:
        strategies.append("Non-SEC / International entity detected: Prioritize GLEIF, Wikipedia, and Annual Report PDFs.")
        strategies.append("Query global LEI / GLEIF registries for ultimate parent and child entities.")
        strategies.append("Crawl official web sitemaps, investor relations, and group structure pages.")
        strategies.append("Deep-search PDF financial statements and consolidated annual reports.")
    else:
        if coverage.get("sec", 1.0) < 0.5:
            strategies.append("Search historical SEC Exhibit 21 filings.")
        if coverage.get("registry", 1.0) < 0.5:
            strategies.append("Query global LEI / GLEIF registries.")
        if coverage.get("website", 1.0) < 0.5:
            strategies.append("Crawl corporate sitemaps and legal copyright footers.")
            
    if not strategies:
        strategies.append("All primary discovery strategies are healthy and saturated.")
        
    summary["recommended_strategies"] = strategies
    logs.append(f"Adaptive Strategy Engine recommends: {', '.join(strategies)}")
    
    return {
        **state,
        "execution_summary": {
            **summary,
            "coverage_report": coverage,
            "is_sec_registered": is_sec
        },
        "logs": logs
    }
