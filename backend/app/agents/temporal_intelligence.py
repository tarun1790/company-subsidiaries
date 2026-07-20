import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.agents.state import AgentState
from app.core.logging import logger

def parse_iso_date(date_str: Optional[str]) -> Optional[str]:
    """Helper to convert raw text date expressions into ISO 8601 YYYY-MM-DD string format."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", date_str)
    if match:
        y, m, d = match.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"
    match_yr = re.search(r"\b(19\d{2}|20\d{2})\b", date_str)
    if match_yr:
        return f"{match_yr.group(1)}-01-01"
    return None

def filter_as_of_date_edges(edges: List[Dict[str, Any]], as_of_date_str: str) -> List[Dict[str, Any]]:
    """Filters knowledge graph edges based on historical point-in-time bounds:
    valid_from <= as_of_date AND (valid_to > as_of_date OR valid_to IS NULL).
    """
    if not as_of_date_str:
        return edges
    
    as_of = parse_iso_date(as_of_date_str)
    if not as_of:
        return edges

    filtered = []
    for e in edges:
        v_from = parse_iso_date(e.get("valid_from"))
        v_to = parse_iso_date(e.get("valid_to"))

        # Rule 1: valid_from <= as_of_date (or valid_from is unknown)
        if v_from and v_from > as_of:
            continue
            
        # Rule 2: valid_to > as_of_date or valid_to is None
        if v_to and v_to <= as_of:
            continue

        filtered.append(e)

    return filtered

async def temporal_intelligence_agent(state: AgentState) -> AgentState:
    """Agent Stage 19: Time-bounds relationship edges and performs historical point-in-time filtering."""
    logs = state.get("logs", [])
    as_of_date = state.get("as_of_date")
    kg = state.get("knowledge_graph") or {}
    edges = kg.get("edges", [])

    logs.append(f"Running Temporal Intelligence Agent (as_of_date: {as_of_date or 'Latest'})...")

    updated_edges = []
    for e in edges:
        evidences = e.get("evidences", [])
        v_from = e.get("valid_from")
        
        # If valid_from missing, check evidence text quotes for date references
        if not v_from and evidences:
            for ev in evidences:
                txt = ev.get("extracted_text", "")
                extracted_date = parse_iso_date(txt)
                if extracted_date:
                    v_from = extracted_date
                    break

        updated_edge = {
            **e,
            "valid_from": v_from or datetime.utcnow().strftime("%Y-%m-%d"),
            "valid_to": e.get("valid_to"),
            "status": e.get("status") or ("Active" if not e.get("valid_to") else "Historical")
        }
        updated_edges.append(updated_edge)

    # Filter by as_of_date if specified
    if as_of_date:
        filtered = filter_as_of_date_edges(updated_edges, as_of_date)
        logs.append(f"Temporal As-Of Date ({as_of_date}) filtered graph edges: {len(filtered)} active (from {len(edges)} total).")
        updated_edges = filtered

    updated_kg = {**kg, "edges": updated_edges}
    
    return {
        **state,
        "knowledge_graph": updated_kg,
        "logs": logs
    }
