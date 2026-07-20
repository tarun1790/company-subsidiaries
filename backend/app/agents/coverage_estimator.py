import re
from typing import Dict, List, Any
from app.agents.state import AgentState
from app.core.logging import logger

async def coverage_estimator_agent(state: AgentState) -> AgentState:
    """Agent 12: Computes coverage and completeness metrics across all active discovery channels."""
    logs = state.get("logs") or []
    subs = state.get("subsidiaries") or []
    
    sec_count = 0
    web_count = 0
    reg_count = 0
    doc_count = 0
    
    for s in subs:
        sources = {ev.get("source_type") for ev in s.get("evidences", [])}
        if "SEC Filings" in sources: sec_count += 1
        if "Official Website" in sources: web_count += 1
        if "Public Registry" in sources: reg_count += 1
        if "Web Research" in sources: doc_count += 1
        
    total = len(subs)
    sec_cov = sec_count / total if total > 0 else 1.0
    web_cov = web_count / total if total > 0 else 1.0
    reg_cov = reg_count / total if total > 0 else 1.0
    doc_cov = doc_count / total if total > 0 else 1.0
    
    overall_cov = 0.4 * sec_cov + 0.3 * reg_cov + 0.2 * web_cov + 0.1 * doc_cov
    
    coverage_score = {
        "overall": round(overall_cov, 3),
        "sec": round(sec_cov, 3),
        "registry": round(reg_cov, 3),
        "document": round(doc_cov, 3),
        "website": round(web_cov, 3)
    }
    
    logs.append(f"Coverage Estimator: Computed completeness score of {overall_cov * 100:.1f}%.")
    return {
        **state,
        "coverage_score": coverage_score,
        "logs": logs
    }
