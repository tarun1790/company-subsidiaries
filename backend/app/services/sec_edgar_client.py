import httpx
import json
import re
import os
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
from app.core.logging import logger
from app.core.redis_cache import cache_manager

class SECEdgarClient:
    def __init__(self):
        # SEC EDGAR requires a specific User-Agent containing contact details
        self.headers = {
            "User-Agent": "CorporateSubsidiaryIntelligencePlatform tarun.jampani45@gmail.com",
            "Accept-Encoding": "gzip, deflate"
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=30.0, follow_redirects=True)

    async def get_cik_by_name_or_ticker(self, name_or_ticker: str) -> Optional[str]:
        """Looks up a company's CIK from the SEC's master ticker list."""
        cache_key = f"cik:{name_or_ticker.lower()}"
        cached = await cache_manager.get(cache_key)
        if cached:
            return cached

        # Try local file first to bypass DNS blocks
        local_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "company_tickers.json"
        )
        data = None
        if os.path.exists(local_path):
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info("Loaded SEC company tickers list from local cache file.")
            except Exception as le:
                logger.warning(f"Failed to read local SEC tickers file: {str(le)}")

        if not data:
            try:
                # Fetch master ticker list from SEC (fallback)
                url = "https://www.sec.gov/files/company_tickers.json"
                response = await self.client.get(url)
                if response.status_code == 200:
                    data = response.json()
                else:
                    logger.error(f"Failed to fetch SEC ticker list: {response.status_code}")
            except Exception as e:
                logger.error(f"Network error fetching SEC ticker list: {str(e)}")

        if not data:
            return None

        try:
            search_str = name_or_ticker.strip().lower()
            
            # Exact ticker match first
            for item in data.values():
                if item["ticker"].lower() == search_str:
                    cik = str(item["cik_str"]).zfill(10)
                    await cache_manager.set(cache_key, cik)
                    return cik

            # Fuzzy name match
            for item in data.values():
                if search_str in item["title"].lower():
                    cik = str(item["cik_str"]).zfill(10)
                    await cache_manager.set(cache_key, cik)
                    return cik
                    
        except Exception as e:
            logger.error(f"Error looking up CIK for {name_or_ticker}: {str(e)}")
            
        return None

    async def get_latest_filings(self, cik: str) -> List[Dict[str, Any]]:
        """Retrieves recent filings for a given CIK."""
        cache_key = f"filings:{cik}"
        cached_json = await cache_manager.get_json(cache_key)
        if cached_json:
            return cached_json

        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                logger.error(f"Failed to fetch submissions for CIK {cik}: {response.status_code}")
                return []
            
            data = response.json()
            recent_filings = data.get("filings", {}).get("recent", {})
            
            filings = []
            if recent_filings:
                num_filings = len(recent_filings.get("accessionNumber", []))
                for i in range(num_filings):
                    filings.append({
                        "accessionNumber": recent_filings["accessionNumber"][i],
                        "form": recent_filings["form"][i],
                        "filingDate": recent_filings["filingDate"][i],
                        "reportDate": recent_filings["reportDate"][i],
                        "primaryDocument": recent_filings["primaryDocument"][i],
                        "primaryDocDescription": recent_filings["primaryDocDescription"][i],
                    })
            
            await cache_manager.set_json(cache_key, filings, expire=43200) # cache for 12 hours
            return filings
        except Exception as e:
            logger.error(f"Error fetching filings for CIK {cik}: {str(e)}")
            return []

    async def get_exhibit_21(self, cik: str, accession_number: str) -> Optional[str]:
        """Attempts to find and retrieve Exhibit 21 (List of Subsidiaries) for a filing."""
        clean_acc = accession_number.replace("-", "")
        # Step 1: Fetch directory listing for this filing
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{clean_acc}/"
        cache_key = f"ex21_content:{cik}:{accession_number}"
        cached = await cache_manager.get(cache_key)
        if cached:
            return cached

        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, "html.parser")
            ex21_link = None
            
            # Find links ending with ex21, ex-21, or containing exhibit 21
            for link in soup.find_all("a", href=True):
                href = link["href"]
                text = link.get_text().lower()
                href_lower = href.lower()
                
                # Check patterns like ex21.htm, ex-21.htm, ex_21.htm, ex21_1.htm, etc.
                if re.search(r"ex[-_]?21[a-z0-9_-]*\.(htm|txt)", href_lower) or "exhibit 21" in text or "ex-21" in text:
                    ex21_link = href
                    break
            
            if ex21_link:
                # Resolve full URL
                if not ex21_link.startswith("http"):
                    # Relative to standard archives path
                    ex21_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{clean_acc}/{ex21_link.split('/')[-1]}"
                else:
                    ex21_url = ex21_link

                logger.info(f"Found Exhibit 21 URL: {ex21_url}")
                doc_response = await self.client.get(ex21_url)
                if doc_response.status_code == 200:
                    content = doc_response.text
                    await cache_manager.set(cache_key, content, expire=86400)
                    return content
                    
        except Exception as e:
            logger.error(f"Error fetching Exhibit 21 for CIK {cik}, Acc {accession_number}: {str(e)}")
            
        return None

    def parse_exhibit_21_html(self, html_content: str) -> List[Dict[str, Any]]:
        """Parses the HTML text of Exhibit 21 to extract subsidiary names and locations."""
        subsidiaries = []
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Clean text
        text = soup.get_text()
        
        # Find tables - Exhibit 21 often lists subsidiaries in a table
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cols = [col.get_text(strip=True) for col in row.find_all(["td", "th"])]
                cols = [c for c in cols if c]
                if len(cols) >= 2:
                    # Look for typical formats: [Name, Jurisdiction] or [Name, Percent, Jurisdiction]
                    name = cols[0]
                    # Filter out header labels
                    if any(h in name.lower() for h in ["name of", "subsidiary", "jurisdiction", "state of", "country", "incorporation"]):
                        continue
                    
                    jurisdiction = cols[-1]
                    percent = cols[1] if len(cols) > 2 else "100%"
                    
                    # Clean name (remove extra spaces, characters)
                    clean_name = re.sub(r'\s+', ' ', name).strip()
                    clean_juri = re.sub(r'\s+', ' ', jurisdiction).strip()
                    
                    if len(clean_name) > 3 and len(clean_juri) > 2:
                        subsidiaries.append({
                            "name": clean_name,
                            "country": clean_juri,
                            "ownership": percent,
                            "relationship_type": "Subsidiary",
                            "notes": "Extracted from SEC EDGAR Exhibit 21 table structure."
                        })

        # Fallback if no tables or tables returned no subsidiaries: use regex on lines
        if not subsidiaries:
            lines = text.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Match lines containing a company name and a state/country suffix/parenthesis or tab separation
                # e.g., "Microsoft Ireland Operations Limited (Ireland)" or "Microsoft Corp. - Delaware"
                match = re.search(r"([A-Za-z0-9\s\.,&'\-\(\)]+)\s+[\(-\u2013]\s*([A-Z][A-Za-z\s\.]+)\s*\)?", line)
                if match:
                    name = match.group(1).strip()
                    jurisdiction = match.group(2).strip()
                    if len(name) > 3 and len(jurisdiction) > 2 and not any(h in name.lower() for h in ["name", "subsidiary", "jurisdiction", "incorporation"]):
                        subsidiaries.append({
                            "name": name,
                            "country": jurisdiction,
                            "ownership": "100%",
                            "relationship_type": "Subsidiary",
                            "notes": "Extracted from SEC EDGAR Exhibit 21 text line-match."
                        })
                        
        return subsidiaries

sec_client = SECEdgarClient()
