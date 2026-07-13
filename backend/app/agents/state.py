from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    query: str
    company_info: Dict[str, Any]      # Resolved company parameters (legal_name, domain, ticker, cik, hq_country)
    subsidiaries: List[Dict[str, Any]] # Consolidated subsidiaries list
    logs: List[str]                   # Execution logs showing pipeline step updates
    pdf_path: Optional[str]
    excel_path: Optional[str]
    csv_path: Optional[str]
    json_path: Optional[str]
    errors: List[str]
