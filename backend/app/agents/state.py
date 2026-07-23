import operator
import time
from typing import TypedDict, List, Dict, Any, Optional, Annotated

def emit_node_telemetry(stage_name: str, state: dict, started_at: float, status: str):
    duration_ms = int((time.time() - started_at) * 1000)

    telemetry = {
        "stage": stage_name,
        "status": status,
        "duration_ms": duration_ms,
        "input_counts": {
            "source_documents": len(state.get("source_documents", [])),
            "document_chunks": len(state.get("document_chunks", [])),
            "raw_claims": len(state.get("raw_claims", [])),
            "candidate_entities": len(state.get("candidate_entities", [])),
            "normalized_entities": len(state.get("normalized_entities", [])),
            "relationships": len(state.get("relationships", [])),
            "evidence_records": len(state.get("evidence_records", [])),
        },
        "warnings": state.get("warnings", [])[-5:],
        "errors": state.get("errors", [])[-5:],
    }

    state.setdefault("telemetry", []).append(telemetry)

def list_merger(current: Optional[List[Any]], update: Optional[List[Any]]) -> List[Any]:
    if current is None:
        current = []
    if update is None:
        update = []
    merged = []
    seen = set()
    for item in current:
        if isinstance(item, dict):
            key = str(sorted(item.items()))
        else:
            key = item
        if key not in seen:
            seen.add(key)
            merged.append(item)
    for item in update:
        if isinstance(item, dict):
            key = str(sorted(item.items()))
        else:
            key = item
        if key not in seen:
            seen.add(key)
            merged.append(item)
    return merged

class AgentState(TypedDict, total=False):
    query: str
    company_info: Dict[str, Any]       # Resolved company parameters (legal_name, domain, ticker, cik, hq_country)
    subsidiaries: List[Dict[str, Any]]  # Consolidated subsidiaries list
    
    # Canonical Pipeline Keys for v2.1 State Contracts
    source_documents: Annotated[List[Dict[str, Any]], list_merger]
    document_chunks: Annotated[List[Dict[str, Any]], list_merger]
    classified_documents: Annotated[List[Dict[str, Any]], list_merger]
    raw_claims: Annotated[List[Dict[str, Any]], list_merger]
    candidate_entities: Annotated[List[Dict[str, Any]], list_merger]
    normalized_entities: Annotated[List[Dict[str, Any]], list_merger]
    fused_claims: Annotated[List[Dict[str, Any]], list_merger]
    evidence_records: Annotated[List[Dict[str, Any]], list_merger]
    relationships: Annotated[List[Dict[str, Any]], list_merger]
    verification_results: Annotated[List[Dict[str, Any]], list_merger]
    warnings: Annotated[List[Dict[str, Any]], list_merger]
    errors: Annotated[List[str], list_merger]
    logs: Annotated[List[str], list_merger]

    # Namespaced collector output lists
    sec_results: List[Dict[str, Any]]
    website_results: List[Dict[str, Any]]
    registry_results: List[Dict[str, Any]]
    search_results: List[Dict[str, Any]]
    domain_results: List[Dict[str, Any]]
    extracted_document_results: List[Dict[str, Any]]
    
    discovered_documents: Annotated[List[str], list_merger]
    document_contents: Dict[str, str]
    knowledge_graph: Dict[str, Any]
    pdf_path: Optional[str]
    excel_path: Optional[str]
    csv_path: Optional[str]
    json_path: Optional[str]
    
    # Execution & Telemetry Control
    current_iteration: int
    explored_entities: List[str]
    pending_targets: List[Dict[str, Any]]
    coverage_score: Dict[str, Any]
    as_of_date: Optional[str]
    telemetry: Annotated[List[Dict[str, Any]], list_merger]
