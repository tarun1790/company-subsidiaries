from typing import Dict, List, Any
from app.agents.state import AgentState
from app.core.logging import logger

async def discovery_strategy_engine_agent(state: AgentState) -> AgentState:
    """Agent 13: Identifies missing parent/child links and targets next collection strategies."""
    logs = state.get("logs") or []
    coverage = state.get("coverage_score") or {"overall": 0.0}
    summary = state.get("execution_summary") or {}
    
    logs.append("Running Discovery Strategy Engine...")
    
    strategies = []
    if coverage.get("sec", 1.0) < 0.5:
        strategies.append("Search historical SEC Exhibit 21 filings.")
    if coverage.get("registry", 1.0) < 0.5:
        strategies.append("Query global LEI / GLEIF registries.")
    if coverage.get("website", 1.0) < 0.5:
        strategies.append("Crawl corporate sitemaps and legal copyright footers.")
    if coverage.get("document", 1.0) < 0.5:
        strategies.append("Deep-search press releases and acquisition announcements.")
        
    if not strategies:
        strategies.append("All primary discovery strategies are healthy and saturated.")
        
    summary["recommended_strategies"] = strategies
    logs.append(f"Strategy Engine recommends: {', '.join(strategies)}")
    
    return {
        **state,
        "execution_summary": {
            **summary,
            "coverage_report": coverage
        },
        "logs": logs
    }
