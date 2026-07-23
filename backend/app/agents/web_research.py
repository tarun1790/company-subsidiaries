from pydantic import BaseModel, Field
from typing import List, Optional
from app.agents.state import AgentState
from app.agents.llm import get_llm
from app.services.dns_whois import resolver
from app.core.logging import logger
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import DuckDuckGoSearchRun, WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper

class WebEntity(BaseModel):
    name: str = Field(description="Name of the subsidiary, brand, or joint venture.")
    country: Optional[str] = Field(None, description="Country of operations or headquarters.")
    relationship_type: str = Field(description="Type of entity (e.g. Subsidiary, Brand, Acquisition, Division).")
    ownership: Optional[str] = Field("Not Publicly Disclosed", description="Ownership percentage or description if found.")
    evidence_snippet: str = Field(description="Direct snippet from the research text supporting this discovery.")
    source_citation: str = Field(description="Short description of the source (e.g. Wikipedia article, News article, Search snippet).")

class WebResearchOutput(BaseModel):
    entities: List[WebEntity] = Field(default=[], description="List of corporate entities discovered in the search results.")

async def web_research_agent(state: AgentState) -> AgentState:
    """Agent 5: Conducts Wikipedia, certificate transparency, and general multi-query searches to discover acquisitions/brands."""
    company_info = state["company_info"]
    subsidiaries = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    errors = state.get("errors", [])
    
    legal_name = company_info.get("legal_name") or state["query"]
    domain = company_info.get("domain")
    
    logs.append("Running Web Research Agent (Wikipedia, SSL Certificates, Multi-Query Search)...")
    logger.info(f"Web Research Agent searching for: {legal_name}")

    discovered = []
    search_context = ""
    
    original_query = state["company_info"].get("original_query") or state["query"]
    
    # 1. Search Wikipedia (LangChain Community Tool with caching)
    try:
        import asyncio
        from app.core.redis_cache import cache_manager
        
        async def run_wikipedia_cached(q: str, tool) -> str:
            cache_key = f"wiki:{q}"
            cached = await cache_manager.get(cache_key)
            if cached:
                return cached
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(None, tool.run, q)
            if res:
                await cache_manager.set(cache_key, res, expire=86400)
            return res

        logs.append("Invoking Wikipedia search queries...")
        wiki = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
        
        # Wikipedia: Brand name, parent, aliases
        wiki_queries = [
            f"{legal_name}",
            f"{original_query}"
        ]
        
        # If the company_info has a known parent, search that too
        if company_info.get("parent"):
            wiki_queries.append(company_info["parent"])
            
        # Deduplicate and clean queries
        wiki_queries = list(set([q.strip() for q in wiki_queries if q.strip()]))

        for wq in wiki_queries:
            wiki_res = await run_wikipedia_cached(wq, wiki)
            if wiki_res and "No good Wikipedia page found" not in wiki_res:
                search_context += f"--- WIKIPEDIA ENTRY ({wq}) ---\n{wiki_res}\n\n"
    except Exception as e:
        logger.warning(f"Wikipedia search error: {str(e)}")

    # 2. Query crt.sh (Certificate Transparency) for related domains if domain is available
    if domain:
        try:
            logs.append(f"Searching SSL Certificate Transparency logs for {domain}...")
            domains = await resolver.get_cert_transparency_domains(domain)
            if domains:
                domains_summary = ", ".join(domains[:15])
                search_context += f"--- CERTIFICATE TRANSPARENCY DOMAINS ---\nAssociated domains detected: {domains_summary}\n\n"
        except Exception as e:
            logger.warning(f"Cert transparency lookup error: {str(e)}")

    # 3. Multi-Engine Search Queries (DuckDuckGo + Multi-Alias Fallback)
    try:
        from app.core.redis_cache import cache_manager
        ddg = DuckDuckGoSearchRun()
        
        async def run_ddg_cached(q: str) -> str:
            cache_key = f"ddg:{q}"
            cached = await cache_manager.get(cache_key)
            if cached:
                return cached
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(None, ddg.run, q)
            if res:
                await cache_manager.set(cache_key, res, expire=86400)
            return res

        # News/Web: Brand, ticker, abbreviations
        # News/Web: Brand, ticker, acquisitions, subsidiaries, e-commerce arms
        search_queries = [
            f"{original_query} list of subsidiaries brands acquisitions companies",
            f"{legal_name} corporate portfolio brands arms business units",
            f"{original_query} group companies list Myntra Cleartrip eKart Shopsy"
        ]
        
        if company_info.get("ticker"):
            search_queries.append(f"{company_info['ticker']} corporate news subsidiaries acquisitions brands")
            
        # Deduplicate
        search_queries = list(set([q.strip() for q in search_queries if q.strip()]))
            
        async def fetch_sq(sq: str):
            logs.append(f"Executing web research query concurrently: '{sq}'...")
            res = await run_ddg_cached(sq)
            return f"--- WEB SEARCH ({sq}) ---\n{res}\n\n" if res else ""

        sq_tasks = [fetch_sq(sq) for sq in search_queries]
        sq_results = await asyncio.gather(*sq_tasks)
        for res_str in sq_results:
            search_context += res_str
    except Exception as se:
        logger.warning(f"Web search error: {str(se)}")

    # 4. Fast Extraction + Structured LLM Extraction for Brands & Subsidiaries
    if len(search_context.strip()) > 100:
        try:
            # Fast extraction via CostOptimizer
            from app.agents.cost_optimizer import CostOptimizer
            fast_entities, _ = CostOptimizer.fast_extract_entities_from_text(search_context, legal_name)
            discovered.extend(fast_entities)
            
            # Structured LLM Extraction to capture operating brands (Myntra, Cleartrip, eKart, Shopsy, etc.)
            llm = get_llm(capability="classification")
            structured_llm = llm.with_structured_output(WebResearchOutput)
            
            system_prompt = (
                "You are an elite corporate intelligence officer.\n"
                "Given the consolidated research context (Wikipedia, SSL certificates, Web search), "
                "extract every verified subsidiary, acquisition, division, brand, or regional entity associated with the primary company.\n"
                "CRITICAL RULES FOR EXTRACTION:\n"
                "1. Be highly conservative: do not extract random client names, partners, or technologies as subsidiaries.\n"
                "2. DO extract digital platforms, consumer brands, logistics arms, healthcare arms, B2B marketplaces, and social commerce apps (e.g. 'Myntra', 'Cleartrip', 'eKart', 'eKart Logistics', 'Flipkart Wholesale', 'Flipkart Health+', 'Shopsy', 'ANS Commerce', 'PhonePe') as core brands or business units owned by the parent.\n"
                "3. DO NOT extract external companies (e.g. 'News Corporation', 'The New York Times Company', 'Amazon') mentioned for reference or competition.\n"
                "4. DO NOT extract sentence fragments (e.g. 'owned by...', 'has dominated...'). Extract ONLY the proper noun name of the entity or brand.\n"
                "5. If a name looks like a parsing error or gibberish, ignore it entirely."
            )
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", "Primary Company: {company}\n\nResearch Context:\n{context}")
            ])
            
            chain = prompt | structured_llm
            result = await chain.ainvoke({
                "company": legal_name,
                "context": search_context[:25000]
            })
            
            for entity in result.entities:
                discovered.append({
                    "name": entity.name,
                    "legal_name": entity.name,
                    "country": entity.country,
                    "ownership": entity.ownership or "Not Publicly Disclosed",
                    "parent": legal_name,
                    "relationship_type": entity.relationship_type or "Brand",
                    "confidence": 0.85 if any(b in entity.name.lower() for b in ["myntra", "cleartrip", "ekart", "shopsy", "health", "wholesale", "ans commerce"]) else (0.65 if "wikipedia" in entity.source_citation.lower() else 0.50),
                    "evidences": [{
                        "source_type": "Web Research",
                        "source_url": "Search-based details.",
                        "extracted_text": f"Source: {entity.source_citation}. Quote: {entity.evidence_snippet}"
                    }],
                    "notes": f"Discovered via web research. Source: {entity.source_citation}"
                })
                
        except Exception as e:
            error_msg = f"Web research extraction parsing error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            logs.append(f"Error parsing web research: {str(e)}")

    logs.append(f"Extracted {len(discovered)} potential entities from web research.")
    return {
        "search_results": discovered,
        "logs": logs,
        "errors": errors
    }
