import httpx
import asyncio
from typing import Optional, List, Dict, Any
from app.core.logging import logger
from app.core.redis_cache import cache_manager

class GLEIFClient:
    """GLEIF REST API adapter for Global Legal Entity Identifier (LEI) parent-child relationships."""
    def __init__(self):
        self.base_url = "https://api.gleif.org/api/v1"
        
    async def get_lei_by_name(self, company_name: str) -> Optional[Dict[str, Any]]:
        cache_key = f"gleif_lei:{company_name.lower().strip()}"
        cached = await cache_manager.get_json(cache_key)
        if cached:
            return cached

        url = f"{self.base_url}/lei-records"
        params = {"filter[entity.legalName]": company_name, "page[size]": 1}
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", [])
                    if items:
                        item = items[0]
                        attr = item.get("attributes", {}).get("entity", {})
                        res = {
                            "lei": item.get("id"),
                            "legal_name": attr.get("legalName", {}).get("name"),
                            "jurisdiction": attr.get("jurisdiction"),
                            "country": attr.get("legalAddress", {}).get("country"),
                            "entity_status": attr.get("status"),
                            "source_tier": 2
                        }
                        await cache_manager.set_json(cache_key, res, expire=86400)
                        return res
        except Exception as e:
            logger.error(f"GLEIF LEI lookup error for {company_name}: {str(e)}")
            
        return None

    async def get_parent_relationships(self, lei: str) -> Dict[str, Any]:
        """Retrieves Direct Parent and Ultimate Parent LEI records for a given LEI."""
        cache_key = f"gleif_parents:{lei}"
        cached = await cache_manager.get_json(cache_key)
        if cached:
            return cached

        url = f"{self.base_url}/lei-records/{lei}/direct-parent"
        parents = {"direct_parent": None, "ultimate_parent": None}
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    item = data.get("data", {})
                    if item:
                        attr = item.get("attributes", {}).get("entity", {})
                        parents["direct_parent"] = {
                            "lei": item.get("id"),
                            "legal_name": attr.get("legalName", {}).get("name"),
                            "country": attr.get("legalAddress", {}).get("country"),
                            "source_tier": 2
                        }
        except Exception as e:
            logger.debug(f"GLEIF direct parent fetch error for {lei}: {str(e)}")
            
        await cache_manager.set_json(cache_key, parents, expire=86400)
        return parents

gleif_client = GLEIFClient()
