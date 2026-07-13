import httpx
from typing import List, Dict, Any
from app.core.logging import logger
from app.core.redis_cache import cache_manager

class GLEIFClient:
    def __init__(self):
        self.headers = {
            "User-Agent": "CorporateSubsidiaryIntelligencePlatform tarun.jampani45@gmail.com",
            "Accept": "application/vnd.api+json"
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=15.0)

    async def search_lei(self, company_name: str) -> List[Dict[str, Any]]:
        """Queries GLEIF API for LEI records of a company."""
        cache_key = f"gleif:{company_name.lower()}"
        cached = await cache_manager.get_json(cache_key)
        if cached:
            return cached

        results = []
        url = f"https://api.gleif.org/api/v1/lei-records?filter[fulltext]={company_name}"
        try:
            response = await self.client.get(url)
            if response.status_code == 200:
                payload = response.json()
                data_entries = payload.get("data", [])
                for entry in data_entries:
                    attributes = entry.get("attributes", {})
                    legal_name = attributes.get("legalName", {}).get("name")
                    lei = entry.get("id")
                    
                    entity_details = attributes.get("entity", {})
                    country = entity_details.get("legalAddress", {}).get("country")
                    status = entity_details.get("status")
                    
                    if legal_name and lei:
                        results.append({
                            "name": legal_name,
                            "legal_name": legal_name,
                            "country": country or "Global",
                            "registration_number": lei,
                            "ownership": "100%",
                            "relationship_type": "Subsidiary",
                            "notes": f"Registry source: GLEIF LEI code: {lei}. Status: {status}."
                        })
            else:
                logger.error(f"GLEIF API failed with status {response.status_code}")
        except Exception as e:
            logger.error(f"GLEIF API request failed: {str(e)}")

        await cache_manager.set_json(cache_key, results, expire=86400 * 7)
        return results

gleif_client = GLEIFClient()
