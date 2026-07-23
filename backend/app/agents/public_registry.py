from app.agents.state import AgentState
import re
from app.services.open_corporates import opencorporates
from app.services.gleif import gleif_client
from app.core.logging import logger

async def public_registry_agent(state: AgentState) -> AgentState:
    """Agent 4: Queries OpenCorporates and government registries for legal registration numbers."""
    company_info = state["company_info"]
    subsidiaries = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    errors = state.get("errors", [])
    
    legal_name = company_info.get("legal_name") or state["query"]
    logs.append(f"Searching public registries for '{legal_name}'...")
    logger.info(f"Public Registry Agent searching for: {legal_name}")

    discovered = []
    try:
        # Iterate over the fallback search plan for the main target
        search_plan = company_info.get("search_plan", [legal_name])
        main_target_hits = False
        
        for plan_term in search_plan:
            logs.append(f"Querying OpenCorporates fallback term: '{plan_term}'")
            try:
                records = await opencorporates.search_company(plan_term)
                if records:
                    main_target_hits = True
                    for rec in records:
                        discovered.append({
                            "name": rec["name"],
                            "legal_name": rec.get("legal_name") or rec["name"],
                            "country": rec.get("country"),
                            "ownership": "Not Publicly Disclosed", 
                            "parent": legal_name,
                            "relationship_type": "Subsidiary",
                            "registration_number": rec.get("registration_number"),
                            "confidence": 0.80, 
                            "evidences": [{
                                "source_type": "Public Registry",
                                "source_url": "https://opencorporates.com",
                                "extracted_text": f"Matched registry record: {rec['name']} (Number: {rec.get('registration_number')}, Jurisdiction: {rec.get('country')})"
                            }],
                            "notes": rec.get("notes") or "Matched registry record."
                        })
                    break # Stop fallback if we got hits
            except Exception as oe:
                logger.debug(f"OpenCorporates registry lookup failed for {plan_term}: {str(oe)}")
                
        # If we have some discovered subsidiaries from Agent 2 or 3, lookup them too to verify registration number
        lookup_targets = [s["name"] for s in subsidiaries if s["name"] != legal_name][:2]
        
        for name in lookup_targets:
            # 1. OpenCorporates query for secondary targets
            try:
                records = await opencorporates.search_company(name)
                for rec in records:
                    discovered.append({
                        "name": rec["name"],
                        "legal_name": rec.get("legal_name") or rec["name"],
                        "country": rec.get("country"),
                        "ownership": "Not Publicly Disclosed", 
                        "parent": legal_name,
                        "relationship_type": "Subsidiary",
                        "registration_number": rec.get("registration_number"),
                        "confidence": 0.80, 
                        "evidences": [{
                            "source_type": "Public Registry",
                            "source_url": "https://opencorporates.com",
                            "extracted_text": f"Matched registry record: {rec['name']} (Number: {rec.get('registration_number')}, Jurisdiction: {rec.get('country')})"
                        }],
                        "notes": rec.get("notes") or "Matched registry record."
                    })
            except Exception as oe:
                logger.error(f"OpenCorporates registry lookup failed for {name}: {str(oe)}")

            # 2. GLEIF query: LEI or legal name
            try:
                # Prioritize LEI if it's the main target and we resolved it
                lei_code = company_info.get("lei") if name == legal_name else None
                search_term = lei_code if lei_code else name
                
                gleif_records = await gleif_client.search_lei(search_term)
                for rec in gleif_records:
                    discovered.append({
                        "name": rec["name"],
                        "legal_name": rec["legal_name"],
                        "country": rec["country"],
                        "ownership": "Not Publicly Disclosed",
                        "parent": legal_name,
                        "relationship_type": "Subsidiary",
                        "registration_number": rec["registration_number"],
                        "confidence": 0.85,
                        "evidences": [{
                            "source_type": "Public Registry",
                            "source_url": "https://www.gleif.org",
                            "extracted_text": f"Matched GLEIF LEI Registry: {rec['name']} (LEI: {rec['registration_number']}, Country: {rec['country']})"
                        }],
                        "notes": rec["notes"]
                    })
            except Exception as ge:
                logger.error(f"GLEIF registry lookup failed for {name}: {str(ge)}")

        logs.append(f"Retrieved {len(discovered)} registry matches.")
        return {
            "registry_results": discovered,
            "logs": logs
        }
    except Exception as e:
        error_msg = f"Public registry search error: {str(e)}"
        logger.error(error_msg)
        return {
            "registry_results": [],
            "logs": logs + [f"Error querying registries: {str(e)}"],
            "errors": [error_msg]
        }
