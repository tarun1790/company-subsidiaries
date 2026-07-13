import re
from app.agents.state import AgentState
from app.services.sec_edgar_client import sec_client
from app.core.logging import logger

async def sec_filings_agent(state: AgentState) -> AgentState:
    """Agent 2: Queries SEC EDGAR filings for CIK, fetches 10-K, and extracts Exhibit 21 details."""
    company_info = state["company_info"]
    subsidiaries = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    errors = state.get("errors", [])
    
    cik = company_info.get("cik")
    legal_name = company_info.get("legal_name") or state["query"]
    
    if not cik:
        logs.append("Skipping SEC EDGAR searches (No CIK code resolved).")
        return state

    logs.append(f"Searching SEC EDGAR for CIK {cik}...")
    logger.info(f"SEC Filings Agent searching for CIK: {cik}")

    try:
        filings = await sec_client.get_latest_filings(cik)
        # Find latest 10-K
        ten_k = next((f for f in filings if f["form"] == "10-K"), None)
        
        if not ten_k:
            logs.append("No 10-K filing found in recent SEC submissions.")
            return state

        accession = ten_k["accessionNumber"]
        logs.append(f"Found 10-K filing (Date: {ten_k['filingDate']}). Downloading Exhibit 21...")
        
        ex21_html = await sec_client.get_exhibit_21(cik, accession)
        if not ex21_html:
            logs.append("Exhibit 21 (List of Subsidiaries) was not found in the 10-K directory.")
            return state
            
        logs.append("Exhibit 21 downloaded. Parsing subsidiaries...")
        extracted_subs = sec_client.parse_exhibit_21_html(ex21_html)
        
        clean_acc = accession.replace("-", "")
        evidence_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{clean_acc}/"
        
        discovered = []
        for sub in extracted_subs:
            # Build structured subsidiary item
            sub_name = sub["name"]
            discovered.append({
                "name": sub_name,
                "legal_name": sub_name,
                "country": sub["country"],
                "ownership": sub["ownership"],
                "parent": legal_name,
                "relationship_type": "Subsidiary",
                "confidence": 0.95, # high confidence from official SEC Exhibit 21
                "evidences": [{
                    "source_type": "SEC Filings",
                    "source_url": evidence_url,
                    "extracted_text": f"Found in Exhibit 21 of 10-K: {sub_name} incorporation jurisdiction: {sub['country']}"
                }],
                "notes": sub["notes"]
            })

        logs.append(f"Extracted {len(discovered)} subsidiaries from SEC Exhibit 21.")
        
        return {
            **state,
            "subsidiaries": subsidiaries + discovered,
            "logs": logs
        }
        
    except Exception as e:
        error_msg = f"SEC filings processing error: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)
        logs.append(f"Error searching SEC EDGAR: {str(e)}")
        return {
            **state,
            "logs": logs,
            "errors": errors
        }
