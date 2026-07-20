import re
from app.agents.state import AgentState
from app.core.logging import logger
from langchain_community.tools import DuckDuckGoSearchRun

async def document_discovery_agent(state: AgentState) -> AgentState:
    """Agent 6: Discovers document links (PDFs, Annual Reports, Exhibits, Presentations)."""
    company_info = state["company_info"]
    subsidiaries = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    
    legal_name = company_info.get("legal_name") or state["query"]
    logs.append("Running Document Discovery Agent...")
    logger.info(f"Document Discovery Agent finding PDF files for: {legal_name}")
    
    discovered_docs = []
    
    # 1. Gather URLs already referenced in previous collection nodes
    for sub in subsidiaries:
        for ev in sub.get("evidences", []):
            url = ev.get("source_url")
            if url and url.endswith(".pdf") and url not in discovered_docs:
                discovered_docs.append(url)
                
    # 2. Query DuckDuckGo for PDF Annual Reports & Corporate Governance files
    is_root = state.get("current_iteration", 1) == 1
    has_corporate_indicator = any(ind in legal_name.lower() for ind in ["inc", "llc", "ltd", "corp", "co", "gmbh", "ag", "holdings", "group", "limited", "company", "operating", "subsidiary", "branch"])
    
    if is_root or (len(legal_name) > 5 and has_corporate_indicator):
        try:
            ddg = DuckDuckGoSearchRun()
            search_query = f"{legal_name} annual report filetype:pdf"
            logs.append("Searching corporate registries and search engines for PDF structures...")
            search_res = ddg.run(search_query)
            
            urls = re.findall(r'https?://[^\s<>"]+\.pdf', search_res)
            for url in urls:
                if url not in discovered_docs:
                    discovered_docs.append(url)
        except Exception as e:
            logger.warning(f"Error searching DuckDuckGo for PDFs: {str(e)}")
    else:
        logs.append(f"Skipping PDF web search for generic/non-root target: '{legal_name}'")
        
    logs.append(f"Discovered {len(discovered_docs)} candidate PDF documents for analysis.")
    return {
        "discovered_documents": discovered_docs,
        "logs": logs
    }
