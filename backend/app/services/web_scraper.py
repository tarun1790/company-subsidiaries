import asyncio
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import trafilatura
from playwright.async_api import async_playwright
from app.core.logging import logger
from app.core.redis_cache import cache_manager

class WebScraper:
    def __init__(self):
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

    async def scrape_url(self, url: str, use_browser: bool = True) -> Optional[str]:
        """Scrapes text content from a URL. Uses Playwright if browser-rendering is needed."""
        cache_key = f"webpage:{url}"
        cached = await cache_manager.get(cache_key)
        if cached:
            return cached

        logger.info(f"Scraping page: {url}")
        content = None

        if use_browser:
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(user_agent=self.user_agent)
                    page = await context.new_page()
                    
                    # Set 15s timeout
                    await page.goto(url, timeout=20000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(1000) # Let JavaScript load
                    
                    html = await page.content()
                    # Use trafilatura to extract readable text
                    content = trafilatura.extract(html)
                    if not content:
                        # Fallback to BeautifulSoup
                        soup = BeautifulSoup(html, "html.parser")
                        for element in soup(["script", "style", "nav", "footer", "header"]):
                            element.decompose()
                        content = soup.get_text(separator="\n")
                    
                    await browser.close()
            except Exception as e:
                logger.error(f"Playwright scraping error for {url}: {str(e)}")
                
        # If browser fails or is bypassed, use httpx as a simple HTTP client fallback
        if not content:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    response = await client.get(url, headers={"User-Agent": self.user_agent})
                    if response.status_code == 200:
                        content = trafilatura.extract(response.text)
                        if not content:
                            soup = BeautifulSoup(response.text, "html.parser")
                            for element in soup(["script", "style", "nav", "footer", "header"]):
                                element.decompose()
                            content = soup.get_text(separator="\n")
            except Exception as e:
                logger.error(f"HTTPX scraping fallback error for {url}: {str(e)}")

        if content:
            # Cache the text content for 24 hours
            await cache_manager.set(cache_key, content, expire=86400)
            
        return content

    async def get_corporate_links(self, start_url: str) -> List[str]:
        """Crawls the landing page to find key corporate pages (Investor Relations, About, Locations, etc.)."""
        cache_key = f"links:{start_url}"
        cached_str = await cache_manager.get(cache_key)
        if cached_str:
            try:
                import json
                logger.info(f"Retrieved cached corporate links for: {start_url}")
                return json.loads(cached_str)
            except Exception:
                pass

        logger.info(f"Looking for corporate links on: {start_url}")
        links = []
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=self.user_agent)
                page = await context.new_page()
                await page.goto(start_url, timeout=15000, wait_until="domcontentloaded")
                
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                base_domain = urlparse(start_url).netloc
                
                # Check all anchors
                for anchor in soup.find_all("a", href=True):
                    href = anchor["href"]
                    text = anchor.get_text().lower()
                    
                    # Match corporate keywords
                    keywords = ["about", "investor", "subsidiaries", "governance", "relations", "structure", "office", "locations", "contact", "legal"]
                    if any(kw in text or kw in href.lower() for kw in keywords):
                        full_url = urljoin(start_url, href)
                        # Check same domain to avoid leaving official site
                        if urlparse(full_url).netloc == base_domain:
                            if full_url not in links:
                                links.append(full_url)
                
                await browser.close()
        except Exception as e:
            logger.error(f"Error searching corporate links on {start_url}: {str(e)}")
            
        if links:
            try:
                import json
                await cache_manager.set(cache_key, json.dumps(links[:8]), expire=86400)
            except Exception:
                pass
        return links[:8] # return top 8 candidates

scraper = WebScraper()
