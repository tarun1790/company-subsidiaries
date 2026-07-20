import httpx
import asyncio
import os
from typing import Optional, List, Dict, Any
from app.core.logging import logger
from app.core.redis_cache import cache_manager

class CompaniesHouseClient:
    """UK Companies House REST API adapter for UK registered entities and PSC control disclosures."""
    def __init__(self):
        self.api_key = os.getenv("COMPANIES_HOUSE_API_KEY", "")
        self.base_url = "https://api.company-information.service.gov.uk"
        self.headers = {"Accept": "application/json"}
        
    async def search_company(self, company_name: str) -> List[Dict[str, Any]]:
        cache_key = f"ch_search:{company_name.lower().strip()}"
        cached = await cache_manager.get_json(cache_key)
        if cached:
            return cached

        url = f"{self.base_url}/search/companies"
        params = {"q": company_name, "items_per_page": 5}
        auth = (self.api_key, "") if self.api_key else None
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params, auth=auth, headers=self.headers)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("items", [])
                    results = []
                    for it in items:
                        results.append({
                            "company_number": it.get("company_number"),
                            "title": it.get("title"),
                            "company_status": it.get("company_status"),
                            "address_snippet": it.get("address_snippet"),
                            "country": "United Kingdom",
                            "source_tier": 1
                        })
                    await cache_manager.set_json(cache_key, results, expire=86400)
                    return results
        except Exception as e:
            logger.error(f"Companies House API search error: {str(e)}")
            
        return []

    async def get_psc_ownership(self, company_number: str) -> List[Dict[str, Any]]:
        """Retrieves Persons of Significant Control (PSC) ownership records."""
        cache_key = f"ch_psc:{company_number}"
        cached = await cache_manager.get_json(cache_key)
        if cached:
            return cached

        url = f"{self.base_url}/company/{company_number}/persons-with-significant-control"
        auth = (self.api_key, "") if self.api_key else None
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, auth=auth, headers=self.headers)
                if resp.status_code == 200:
                    data = resp.json()
                    pscs = []
                    for item in data.get("items", []):
                        name = item.get("name")
                        natures = item.get("natures_of_control", [])
                        ownership_desc = ", ".join(natures)
                        pscs.append({
                            "name": name,
                            "nature_of_control": ownership_desc,
                            "relationship_type": "Parent / Significant Control",
                            "country": "United Kingdom",
                            "source_tier": 1
                        })
                    await cache_manager.set_json(cache_key, pscs, expire=86400)
                    return pscs
        except Exception as e:
            logger.error(f"Companies House PSC error for {company_number}: {str(e)}")
            
        return []

companies_house_client = CompaniesHouseClient()
