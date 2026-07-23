import re
import asyncio
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
        logs.append("CIK missing from Entity Resolution. Attempting fallback CIK resolution via search plan...")
        search_plan = company_info.get("search_plan", [legal_name])
        for plan_term in search_plan:
            try:
                res = await sec_client.get_cik_by_name_or_ticker(plan_term)
                if res and res != "Not found" and not str(res).startswith("SEC lookup"):
                    cik = res
                    logs.append(f"Fallback successful: Found CIK {cik} for term '{plan_term}'")
                    break
            except Exception:
                continue
                
    if not cik:
        logs.append("Skipping SEC EDGAR searches (No CIK code resolved after fallback attempts).")
        return {
            "sec_results": [],
            "logs": logs
        }

    logs.append(f"Searching SEC EDGAR for CIK {cik}...")
    logger.info(f"SEC Filings Agent searching for CIK: {cik}")

    try:
        filings = await sec_client.get_latest_filings(cik)
        # Find up to 3 latest 10-K filings
        ten_ks = [f for f in filings if f["form"] == "10-K"]
        ten_ks = ten_ks[:3]
        
        if not ten_ks:
            logs.append("No 10-K filing found in recent SEC submissions.")
            return {
                "sec_results": [],
                "logs": logs
            }

        logs.append(f"Found {len(ten_ks)} recent 10-K filings. Downloading Exhibit 21 lists concurrently...")

        async def process_one_ten_k(f):
            accession = f["accessionNumber"]
            filing_date_str = f.get("filingDate")
            
            ex21_html = await sec_client.get_exhibit_21(cik, accession)
            if not ex21_html:
                logger.warning(f"Exhibit 21 not found for 10-K accession: {accession}")
                return []
                
            extracted_subs = sec_client.parse_exhibit_21_html(ex21_html)
            clean_acc = accession.replace("-", "")
            evidence_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{clean_acc}/"
            
            results = []
            for sub in extracted_subs:
                sub_name = sub["name"]
                results.append({
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
                        "extracted_text": f"Found in Exhibit 21 of 10-K (Filing Date: {filing_date_str}): {sub_name} incorporation jurisdiction: {sub['country']}"
                    }],
                    "notes": sub["notes"]
                })
            return results

        # Run concurrent downloads
        tasks = [process_one_ten_k(f) for f in ten_ks]
        all_results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        from app.agents.evidence_fusion import get_base_name_key
        
        dedup = {}
        for res_list in all_results_lists:
            if isinstance(res_list, Exception):
                logger.error(f"Error processing historical 10-K filing: {str(res_list)}")
                continue
            for item in res_list:
                key = get_base_name_key(item["name"])
                if not key:
                    continue
                if key not in dedup:
                    dedup[key] = item
                else:
                    # Merge evidence trails
                    existing_item = dedup[key]
                    existing_item["evidences"].extend(item["evidences"])
                    if not existing_item.get("ownership") and item.get("ownership"):
                        existing_item["ownership"] = item["ownership"]
                    if not existing_item.get("country") and item.get("country"):
                        existing_item["country"] = item["country"]

        discovered = list(dedup.values())
        logs.append(f"Extracted and merged {len(discovered)} unique subsidiaries from multiple historical Exhibit 21 filings.")
        
        return {
            "sec_results": discovered,
            "logs": logs
        }
        
    except Exception as e:
        error_msg = f"SEC filings processing error: {str(e)}"
        logger.error(error_msg)
        return {
            "sec_results": [],
            "logs": logs + [f"Error searching SEC EDGAR: {str(e)}"],
            "errors": [error_msg]
        }
