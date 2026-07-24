import asyncio
import re
import json
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
    
    # 1. Search Wikipedia natively via python wikipedia API
    try:
        import wikipedia
        logs.append("Invoking direct Wikipedia API search...")
        
        wiki_queries = [legal_name, original_query]
        if company_info.get("parent"):
            wiki_queries.append(company_info["parent"])
        wiki_queries = list(set([q.strip() for q in wiki_queries if q.strip()]))

        for wq in wiki_queries:
            try:
                loop = asyncio.get_running_loop()
                # Fetch summary first with auto_suggest=False to avoid DDG OpenSearch failures
                def _get_wiki_sum(q):
                    try:
                        return wikipedia.summary(q, auto_suggest=False)
                    except Exception:
                        return None
                summary = await loop.run_in_executor(None, _get_wiki_sum, wq)
                if summary:
                    search_context += f"--- WIKIPEDIA ENTRY ({wq}) ---\n{summary}\n\n"
                    
                # Fetch page content and extract targeted sections (subsidiaries, non-banking, international, operations)
                try:
                    def _get_wiki_page(q):
                        try:
                            return wikipedia.page(q, auto_suggest=False)
                        except Exception:
                            return None
                    page = await loop.run_in_executor(None, _get_wiki_page, wq)
                    if page and page.content:
                        sections = re.findall(r'==+\s*(.*?)\s*==+\n(.*?)(?===+|\Z)', page.content, re.DOTALL)
                        relevant_sections = []
                        keywords = ["subsidiary", "subsidiaries", "non-banking", "international", "operations", "domestic", "brands", "divisions", "acquisitions", "branches", "ventures", "associate", "affiliate", "group"]
                        
                        for heading, sec_text in sections:
                            h_clean = heading.lower()
                            if any(kw in h_clean for kw in keywords):
                                relevant_sections.append(f"=== Wikipedia Section: {heading} ===\n{sec_text[:4000]}")
                        
                        if relevant_sections:
                            logs.append(f"Extracted {len(relevant_sections)} targeted Wikipedia sections for '{wq}'.")
                            search_context += "\n\n".join(relevant_sections) + "\n\n"
                        else:
                            search_context += f"--- WIKIPEDIA FULL PAGE ({wq}) ---\n{page.content[:6000]}\n\n"
                except Exception:
                    pass
            except Exception as w_ex:
                logger.debug(f"Wikipedia lookup for '{wq}' failed: {w_ex}")
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
            f"{original_query} list of group companies joint ventures operating divisions"
        ]
        
        if company_info.get("ticker"):
            search_queries.append(f"{company_info['ticker']} corporate news subsidiaries acquisitions brands")
            
        # Deduplicate
        search_queries = list(set([q.strip() for q in search_queries if q.strip()]))
            
        async def fetch_sq(sq: str):
            logs.append(f"Executing web research query concurrently: '{sq}'...")
            try:
                res = await run_ddg_cached(sq)
                return f"--- WEB SEARCH ({sq}) ---\n{res}\n\n" if res else ""
            except Exception as e:
                logger.warning(f"Web search engine failed for '{sq}': {str(e)}")
                return ""

        sq_tasks = [fetch_sq(sq) for sq in search_queries]
        sq_results = await asyncio.gather(*sq_tasks, return_exceptions=True)
        for res_str in sq_results:
            if isinstance(res_str, str) and res_str:
                search_context += res_str
    except Exception as se:
        logger.warning(f"Web search error: {str(se)}")

    # 4. Vector Embedding & Chunk Retrieval via Qdrant & CrossEncoder
    if len(search_context.strip()) > 20:
        try:
            from app.services.vector_retrieval import VectorRetrievalService
            vector_service = VectorRetrievalService()
            
            # Chunk, generate vector embeddings, and index into Qdrant
            await vector_service.index_document(doc_url=f"web_research_{legal_name}", text=search_context)
            
            # Retrieve top semantically relevant vector chunks
            retrieved_chunks = await vector_service.retrieve_relevant_chunks(
                query=f"{legal_name} subsidiaries brands acquisitions divisions business units non-banking international",
                top_k=8,
                rerank_k=4
            )
            
            if retrieved_chunks:
                focused_context = "\n\n".join([chunk["text"] for chunk in retrieved_chunks])
                logs.append(f"Vector Retrieval: Selected top {len(retrieved_chunks)} reranked vector chunks ({len(focused_context)} chars) for LLM extraction.")
            else:
                focused_context = search_context[:3000]
                
            llm = get_llm(capability="classification")
            system_prompt = (
                "You are an elite corporate intelligence officer.\n"
                "Given the vector-retrieved research context, extract every verified subsidiary, acquisition, division, brand, or regional entity associated with the primary company.\n"
                "CRITICAL RULES FOR EXTRACTION:\n"
                "1. Be highly conservative: do not extract random client names, partners, or technologies as subsidiaries.\n"
                "2. DO extract digital platforms, consumer brands, logistics arms, healthcare arms, B2B marketplaces, and banking/insurance units as core entities owned by the parent.\n"
                "3. DO NOT extract external competitors mentioned for reference.\n"
                "4. DO NOT extract sentence fragments. Extract ONLY the proper noun name of the entity or brand.\n"
                "5. If a name looks like a parsing error or gibberish, ignore it entirely."
            )
            
            json_prompt = (
                f"{system_prompt}\n\n"
                "Return ONLY a valid JSON object with key 'entities' containing a list of objects with fields: name, country, relationship_type, source_citation, evidence_snippet.\n\n"
                f"Primary Company: {legal_name}\nResearch Context:\n{focused_context}\n\nJSON:"
            )
            raw_res = await llm.ainvoke(json_prompt)
            raw_text = raw_res.content if hasattr(raw_res, 'content') else str(raw_res)
            
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if match:
                    try:
                        parsed_json = json.loads(match.group(0))
                        ent_list = parsed_json.get("entities") or parsed_json.get("subsidiaries") or []
                        for item in ent_list:
                            if isinstance(item, str):
                                item_name = item
                                item_country = "Global"
                                item_rel = "Brand"
                            elif isinstance(item, dict):
                                item_name = item.get("name") or item.get("subsidiary")
                                item_country = item.get("country") or "Global"
                                item_rel = item.get("relationship_type") or "Brand"
                            else:
                                continue
                                
                            if item_name:
                                discovered.append({
                                    "name": item_name,
                                    "legal_name": item_name,
                                    "country": item_country,
                                    "ownership": "Not Publicly Disclosed",
                                    "parent": legal_name,
                                    "relationship_type": item_rel,
                                    "confidence": 0.70,
                                    "evidences": [{
                                        "source_type": "Web Research",
                                        "source_url": "Search-based details.",
                                        "extracted_text": f"Discovered via web research for {legal_name}."
                                    }],
                                    "notes": f"Discovered via raw JSON web research."
                                })
                    except Exception as pe:
                        logger.warning(f"Failed to parse raw JSON from Ollama: {pe}")

            if 'result' in locals() and result and hasattr(result, 'entities') and result.entities:
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
