from typing import TypedDict, List, Dict, Any, Optional, Annotated

def list_merger(current: Optional[List[Any]], update: Optional[List[Any]]) -> List[Any]:
    if current is None:
        current = []
    if update is None:
        update = []
    merged = []
    seen = set()
    for item in current:
        if isinstance(item, dict):
            # For dicts, use string representation as key
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

class AgentState(TypedDict):
    query: str
    company_info: Dict[str, Any]      # Resolved company parameters (legal_name, domain, ticker, cik, hq_country)
    subsidiaries: List[Dict[str, Any]] # Consolidated subsidiaries list (single-writer)
    
    # Namespaced collector output lists
    sec_results: List[Dict[str, Any]]
    website_results: List[Dict[str, Any]]
    registry_results: List[Dict[str, Any]]
    search_results: List[Dict[str, Any]]
    domain_results: List[Dict[str, Any]]
    extracted_document_results: List[Dict[str, Any]]
    
    logs: Annotated[List[str], list_merger]                   # Execution logs showing pipeline step updates
    discovered_documents: Annotated[List[str], list_merger]
    document_contents: Dict[str, str]
    knowledge_graph: Dict[str, Any]
    pdf_path: Optional[str]
    excel_path: Optional[str]
    csv_path: Optional[str]
    json_path: Optional[str]
    errors: Annotated[List[str], list_merger]
    
    # NEW state fields
    current_iteration: int
    explored_entities: List[str]
    pending_targets: List[Dict[str, Any]]
    coverage_score: Dict[str, Any]
    evidence_cache: Dict[str, Any]
    source_statistics: Dict[str, Any]
    execution_summary: Dict[str, Any]

