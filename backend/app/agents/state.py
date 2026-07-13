from typing import TypedDict, List, Dict, Any, Optional, Annotated
import operator

class AgentState(TypedDict):
    query: str
    company_info: Dict[str, Any]      # Resolved company parameters (legal_name, domain, ticker, cik, hq_country)
    subsidiaries: Annotated[List[Dict[str, Any]], operator.add] # Consolidated subsidiaries list
    logs: Annotated[List[str], operator.add]                   # Execution logs showing pipeline step updates
    discovered_documents: Annotated[List[str], operator.add]
    document_contents: Dict[str, str]
    knowledge_graph: Dict[str, Any]
    pdf_path: Optional[str]
    excel_path: Optional[str]
    csv_path: Optional[str]
    json_path: Optional[str]
    errors: Annotated[List[str], operator.add]
