from pydantic import BaseModel, Field
from typing import List, Optional
from app.agents.state import AgentState
from app.agents.llm import get_llm
from app.services.web_scraper import scraper
from app.core.logging import logger
from langchain_core.prompts import ChatPromptTemplate

class ExtractedSubsidiary(BaseModel):
    name: str = Field(description="Name of the subsidiary, brand, or division.")
    country: Optional[str] = Field(None, description="Country of incorporation or operations.")
    ownership: Optional[str] = Field("Not Publicly Disclosed", description="Ownership percentage or description (e.g. 50% or Joint Venture).")
    relationship_type: str = Field(description="Type of entity: Subsidiary, Brand, Division, Office, Joint Venture.")
    evidence_quote: str = Field(description="The exact text fragment supporting this extraction.")

class ExtractedList(BaseModel):
    entities: List[ExtractedSubsidiary] = Field(default=[], description="List of corporate entities discovered in the text.")

async def official_website_agent(state: AgentState) -> AgentState:
    """Agent 3: Crawls official website corporate structure, investor, or office pages to extract entities."""
    company_info = state["company_info"]
    subsidiaries = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    errors = state.get("errors", [])
    
    domain = company_info.get("domain")
    legal_name = company_info.get("legal_name") or state["query"]
    
    if not domain:
        logs.append("Skipping Official Website crawler (No domain resolved).")
        return {
            "website_results": [],
            "logs": logs
        }

    # Normalise URL structure
    start_url = f"https://{domain}" if not domain.startswith("http") else domain
    logs.append(f"Crawling corporate links on {domain}...")
    logger.info(f"Official Website Agent crawling domain: {domain}")

    discovered = []
    
    try:
        # Find corporate subpages
        links = await scraper.get_corporate_links(start_url)
        # Always include the start URL itself
        urls_to_scrape = [start_url] + [link for link in links if link != start_url]
        # Limit to top 3 pages to prevent context bloat and rate limits
        urls_to_scrape = urls_to_scrape[:3]
        
        llm = get_llm()
        structured_llm = llm.with_structured_output(ExtractedList)
        
        system_prompt = (
            "You are an expert financial analyst auditing corporate subsidiaries.\n"
            "Given the page text scraped from a company website, extract any subsidiaries, holding companies, joint ventures, divisions, or brands.\n"
            "Include country, ownership (if mentioned), relationship type, and the exact supporting quote.\n"
            "Be highly conservative: do not extract random client names, partners, or technologies as subsidiaries."
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Company Name: {company}\nSource URL: {url}\n\nPage Text:\n{text}")
        ])

        for url in urls_to_scrape:
            logs.append(f"Scraping page: {url}...")
            text = await scraper.scrape_url(url, use_browser=True)
            if not text or len(text.strip()) < 100:
                continue

            # Limit text size to prevent LLM context errors
            shortened_text = text[:15000]
            
            try:
                chain = prompt | structured_llm
                result = await chain.ainvoke({
                    "company": legal_name,
                    "url": url,
                    "text": shortened_text
                })
                
                for entity in result.entities:
                    discovered.append({
                        "name": entity.name,
                        "legal_name": entity.name,
                        "country": entity.country,
                        "ownership": entity.ownership,
                        "parent": legal_name,
                        "relationship_type": entity.relationship_type,
                        "confidence": 0.85, # high confidence from official website
                        "evidences": [{
                            "source_type": "Official Website",
                            "source_url": url,
                            "extracted_text": entity.evidence_quote
                        }],
                        "notes": "Discovered via official website corporate portal crawling."
                    })
            except Exception as le:
                logger.error(f"Error executing LLM extraction on page {url}: {str(le)}")
                
        logs.append(f"Extracted {len(discovered)} potential entities from official website pages.")
        return {
            "website_results": discovered,
            "logs": logs
        }
    except Exception as e:
        error_msg = f"Website crawling error: {str(e)}"
        logger.error(error_msg)
        return {
            "website_results": [],
            "logs": logs + [f"Error crawling official website: {str(e)}"],
            "errors": [error_msg]
        }
