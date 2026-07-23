import json
import asyncio
import re
import httpx
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.agents.state import AgentState
from app.agents.llm import get_llm
from app.services.sec_edgar_client import sec_client
from app.services.gleif import gleif_client
from app.services.open_corporates import opencorporates
from app.services.web_scraper import scraper
from app.core.redis_cache import cache_manager
from app.core.logging import logger
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import DuckDuckGoSearchRun

# ============================================================================
# Pydantic Schemas for Multi-Stage Resolution
# ============================================================================

class ResolvedEntity(BaseModel):
    query_used: str
    canonical_company: str
    official_domain: str
    country: str
    legal_name: str
    registration_number: Optional[str] = None
    cik: Optional[str] = None
    ticker: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    historical_names: List[str] = Field(default_factory=list)
    parent_company: Optional[str] = None
    search_plan: List[str] = Field(default_factory=list)
    confidence: float
    status: str = "success"

class EntityIntelligence(BaseModel):
    is_brand_or_subsidiary: bool = Field(description="Is the input a brand, app, or subsidiary that belongs to a larger parent company?")
    resolved_parent: Optional[str] = Field(None, description="If it's a brand/subsidiary, what is the ultimate parent company name?")
    domain: Optional[str] = Field(None, description="Official website domain")
    ticker: Optional[str] = Field(None, description="Public stock ticker if applicable")

class LegalAliasExtraction(BaseModel):
    legal_name: str = Field(description="The exact legal registered name")
    aliases: List[str] = Field(default_factory=list, description="Common aliases or trade names")
    historical_names: List[str] = Field(default_factory=list, description="Former legal names")

# Programmatic fallbacks
COMMON_BRANDS_FALLBACK = {
    "instagram": ("Meta Platforms, Inc.", "meta.com", "META"),
    "youtube": ("Alphabet Inc.", "google.com", "GOOGL"),
    "cognizant": ("Cognizant Technology Solutions Corporation", "cognizant.com", "CTSH"),
    "google": ("Alphabet Inc.", "google.com", "GOOGL"),
    "aws": ("Amazon.com, Inc.", "amazon.com", "AMZN"),
}

def generate_search_plan(entity: ResolvedEntity, original_query: str) -> List[str]:
    """Generates a prioritized list of search terms for downstream nodes."""
    plan = []
    # 1. Start with the most precise identifier (legal name)
    if entity.legal_name: plan.append(entity.legal_name)
    # 2. Then the canonical company name
    if entity.canonical_company and entity.canonical_company not in plan: plan.append(entity.canonical_company)
    # 3. Ticker is highly specific
    if entity.ticker and entity.ticker not in plan: plan.append(entity.ticker)
    # 4. User's original query
    if original_query and original_query not in plan: plan.append(original_query)
    # 5. Aliases
    for alias in entity.aliases:
        if alias not in plan: plan.append(alias)
    # 6. Parent company
    if entity.parent_company and entity.parent_company not in plan: plan.append(entity.parent_company)
    # 7. Historical names
    for hist in entity.historical_names:
        if hist not in plan: plan.append(hist)
    return plan

async def entity_resolution_agent(state: AgentState) -> AgentState:
    """Agent 1: Resolves user search term into a verified legal entity using a linear multi-stage pipeline."""
    raw_query = state.get("query")
    if isinstance(raw_query, dict):
        query = str(raw_query.get("query") or raw_query.get("company_info", {}).get("legal_name") or "").strip()
    else:
        query = str(raw_query or "").strip()
        
    logs = state.get("logs", [])
    logs.append(f"Initiating V4 Multi-Stage Entity Resolution for: '{query}'...")
    logger.info(f"Initiating Entity Resolution for query: {query}")
    
    query_lower = query.lower().strip()
    cache_key = f"er_canonical_v4:{query_lower}"

    # Stage 0: Cache Check
    cached_data = await cache_manager.get_json(cache_key)
    if cached_data:
        logs.append(f"Cache HIT for '{query}'. Skipping resolution pipeline.")
        company_info = cached_data
        state["query"] = company_info.get("canonical_company", query)
        return {**state, "company_info": company_info, "logs": logs}
        
    logs.append(f"Cache MISS. Proceeding with resolution pipeline...")
    
    parent_name = None
    domain = None
    ticker = None
    
    # Stage 1 & 2 & 3: Brand, Domain, Ticker Detection
    if query_lower in COMMON_BRANDS_FALLBACK:
        parent_name, domain, ticker = COMMON_BRANDS_FALLBACK[query_lower]
        logs.append(f"Stage 1-3 (Programmatic): Resolved '{query}' -> Parent: {parent_name}, Domain: {domain}, Ticker: {ticker}")
    else:
        logs.append("Stage 1-3 (LLM): Running Brand, Domain, and Ticker detection...")
        llm = get_llm(capability="entity_resolution")
        intel_llm = llm.with_structured_output(EntityIntelligence)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a corporate intelligence engine. Identify if the input is a brand/subsidiary, resolve its ultimate parent company, find its official domain, and identify its public stock ticker if it has one."),
            ("user", "Query: {query}")
        ])
        try:
            res = await (prompt | intel_llm).ainvoke({"query": query})
            if res.is_brand_or_subsidiary and res.resolved_parent:
                parent_name = res.resolved_parent
            else:
                parent_name = query
            domain = res.domain
            ticker = res.ticker
            logs.append(f"Detection Results -> Target: {parent_name}, Domain: {domain}, Ticker: {ticker}")
        except Exception as e:
            logger.warning(f"Detection LLM failed: {e}")
            parent_name = query
            
    # Override query with parent if resolved
    target_query = parent_name if parent_name else query
    state["query"] = target_query

    # Stage 4: Legal Name Resolution
    logs.append(f"Stage 4 (Legal Name): Querying public registries for '{target_query}'...")
    legal_name = target_query
    country = "Global"
    reg_number = None
    lei = None
    
    # Check GLEIF
    try:
        gleif_res = await gleif_client.search_lei(target_query)
        if gleif_res:
            legal_name = gleif_res[0]["legal_name"]
            country = gleif_res[0].get("country", "Global")
            reg_number = gleif_res[0].get("registration_number")
            lei = gleif_res[0].get("registration_number")
            logs.append(f"GLEIF match found: {legal_name} (LEI: {lei})")
    except Exception as e:
        logger.debug(f"GLEIF search failed: {e}")
        
    # If no LEI, check OpenCorporates
    if legal_name == target_query:
        try:
            oc_res = await opencorporates.search_company(target_query)
            if oc_res:
                legal_name = oc_res[0].get("legal_name") or oc_res[0]["name"]
                country = oc_res[0].get("country", country)
                reg_number = oc_res[0].get("registration_number")
                logs.append(f"OpenCorporates match found: {legal_name}")
        except Exception as e:
            logger.debug(f"OpenCorporates search failed: {e}")

    # Stage 5: CIK Lookup
    cik = None
    logs.append(f"Stage 5 (CIK Lookup): Searching SEC for '{legal_name}' or ticker '{ticker}'...")
    try:
        # Prefer ticker if available for exact SEC match
        sec_query = ticker if ticker else legal_name
        sec_res = await sec_client.get_cik_by_name_or_ticker(sec_query)
        if sec_res and sec_res != "Not found" and not str(sec_res).startswith("SEC lookup"):
            cik = sec_res
            logs.append(f"SEC match found: CIK {cik}")
    except Exception as e:
        logger.debug(f"SEC CIK lookup failed: {e}")

    # Stage 6: Alias & Historical Expansion
    aliases = []
    historical = []
    logs.append("Stage 6 (Alias Expansion): Searching for trade names and historical aliases...")
    try:
        ddg = DuckDuckGoSearchRun()
        search_text = await asyncio.to_thread(ddg.run, f"{legal_name} former names aliases trading as")
        
        llm = get_llm(capability="entity_resolution")
        alias_llm = llm.with_structured_output(LegalAliasExtraction)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Extract the exact legal name, current aliases, and former/historical names from the search context. Return empty arrays if none found."),
            ("user", "Company: {company}\\nContext:\\n{text}")
        ])
        ext = await (prompt | alias_llm).ainvoke({"company": legal_name, "text": search_text[:5000]})
        aliases = ext.aliases
        historical = ext.historical_names
        if len(aliases) > 0 or len(historical) > 0:
            logs.append(f"Extracted {len(aliases)} aliases and {len(historical)} historical names.")
    except Exception as e:
        logger.warning(f"Alias expansion failed: {e}")

    # Stage 7: Source-Specific Search Planning
    resolved = ResolvedEntity(
        query_used=query,
        canonical_company=parent_name if parent_name else legal_name,
        official_domain=domain or "",
        country=country,
        legal_name=legal_name,
        registration_number=reg_number,
        cik=cik,
        ticker=ticker,
        aliases=aliases,
        historical_names=historical,
        parent_company=parent_name if parent_name and parent_name != legal_name else None,
        confidence=1.0 if cik or reg_number else 0.7
    )
    
    # Generate the fallback plan
    resolved.search_plan = generate_search_plan(resolved, query)
    logs.append(f"Stage 7: Generated Fallback Search Plan: {resolved.search_plan}")

    # Stage 8: Cache Saving
    company_info = resolved.model_dump()
    company_info["status"] = "success"
    # Attach lei explicitly to company_info dict so downstream nodes can use it directly
    if lei:
        company_info["lei"] = lei
        
    await cache_manager.set_json(cache_key, company_info)
    logs.append(f"Stage 8: Successfully cached canonical entity payload.")

    return {
        **state,
        "company_info": company_info,
        "logs": logs
    }
