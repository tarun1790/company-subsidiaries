import os
import httpx
import asyncio
from typing import Optional, Dict, Any, List
from app.core.logging import logger
from app.core.redis_cache import cache_manager

class OpenCorporatesClient:
    def __init__(self):
        self.api_token = os.getenv("OPENCORPORATES_API_TOKEN")
        self.headers = {}
        if self.api_token:
            self.headers["Authorization"] = f"Bearer {self.api_token}"
        self.client = httpx.AsyncClient(headers=self.headers, timeout=15.0)

    async def search_company(self, company_name: str) -> List[Dict[str, Any]]:
        """Queries OpenCorporates for a company name."""
        cache_key = f"opencorp:{company_name.lower()}"
        cached = await cache_manager.get_json(cache_key)
        if cached:
            return cached

        results = []
        if self.api_token:
            url = f"https://api.opencorporates.com/v0.4/companies/search?q={company_name}"
            try:
                response = await self.client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    companies = data.get("results", {}).get("companies", [])
                    for c in companies:
                        comp = c.get("company", {})
                        results.append({
                            "name": comp.get("name"),
                            "legal_name": comp.get("name"),
                            "country": comp.get("jurisdiction_code"),
                            "registration_number": comp.get("company_number"),
                            "relationship_type": "Subsidiary",
                            "notes": f"Registry source: OpenCorporates. Status: {comp.get('current_status')}"
                        })
            except Exception as e:
                logger.error(f"OpenCorporates API error for {company_name}: {str(e)}")
        
        # Fallback to search-based crawling if API is unconfigured or returns nothing
        if not results:
            try:
                # Use DuckDuckGo Search to query OpenCorporates pages
                from langchain_community.tools import DuckDuckGoSearchRun
                search = DuckDuckGoSearchRun()
                # Run search
                query = f"site:opencorporates.com {company_name}"
                raw_search = await asyncio.to_thread(search.run, query)
                
                # Check if we can parse company names or numbers from search results
                # Simple extraction:
                # e.g., "Microsoft Limited - OpenCorporates - Company Number 12345"
                # Let's use basic regex to extract company details
                import re
                company_matches = re.findall(r"([A-Za-z0-9\s\.,&'\-]+)\s+-\s+OpenCorporates.*?(Company Number|number|No\.)\s*([A-Za-z0-9]+)", raw_search, re.IGNORECASE)
                
                for match in company_matches:
                    name = match[0].strip()
                    num = match[2].strip()
                    if name and num:
                        results.append({
                            "name": name,
                            "legal_name": name,
                            "registration_number": num,
                            "notes": "Extracted via OpenCorporates search indexing."
                        })
            except Exception as e:
                logger.debug(f"OpenCorporates fallback search failed for {company_name}: {str(e)}")

        await cache_manager.set_json(cache_key, results, expire=86400 * 3)
        return results

import asyncio # imported to support asyncio.to_thread inside fallback
opencorporates = OpenCorporatesClient()
