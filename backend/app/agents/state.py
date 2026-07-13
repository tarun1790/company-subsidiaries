from typing import TypedDict, List, Dict, Any, Optional, Annotated
import operator

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
    
    logs: Annotated[List[str], operator.add]                   # Execution logs showing pipeline step updates
    discovered_documents: Annotated[List[str], operator.add]
    document_contents: Dict[str, str]
    knowledge_graph: Dict[str, Any]
    pdf_path: Optional[str]
    excel_path: Optional[str]
    csv_path: Optional[str]
    json_path: Optional[str]
    errors: Annotated[List[str], operator.add]
