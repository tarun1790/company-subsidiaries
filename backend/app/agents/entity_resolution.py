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
    is_sec_registered: bool = False
    primary_jurisdiction: str = "US"
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
    is_sec_registered: bool = Field(False, description="Whether the company files Form 10-K/10-Q with the US SEC")
    primary_jurisdiction: str = Field("US", description="Two-letter country code or name of headquarters jurisdiction, e.g. US, RU, IN, GB")

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
    
    # Domain / URL cleaning (e.g. "netflix.com" -> "netflix")
    clean_q = re.sub(r'^(?:https?://)?(?:www\.)?', '', query_lower, flags=re.IGNORECASE)
    clean_q = re.sub(r'\.(?:com|org|net|io|co|in|ai|gov|edu|uk|ca|de|fr|br|jp|kr)$', '', clean_q, flags=re.IGNORECASE).strip()
    if clean_q and len(clean_q) >= 2:
        query_lower = clean_q
        
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
            ("system", "You are a corporate intelligence engine. Identify if the input is a brand, subsidiary, or short name. Resolve it to its true, full legal registered corporate parent company name (e.g., 'kompas' -> 'Kompas Gramedia Group' or 'PT Kompas Media Nusantara'). Find its official domain, and identify its public stock ticker if it has one."),
            ("user", "Query: {query}")
        ])
        try:
            async def _run_intel():
                try:
                    return await (prompt | intel_llm).ainvoke({"query": query})
                except Exception:
                    raw_p = (
                        "You are a corporate intelligence engine. Return ONLY a valid JSON object with keys: 'resolved_parent' (string), 'domain' (string), 'ticker' (string).\n"
                        f"Query: {query}\nJSON:"
                    )
                    raw_res = await llm.ainvoke(raw_p)
                    raw_text = raw_res.content if hasattr(raw_res, 'content') else str(raw_res)
                    match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                    if match:
                        pj = json.loads(match.group(0))
                        return EntityIntelligence(
                            is_brand_or_subsidiary=bool(pj.get("resolved_parent")),
                            resolved_parent=pj.get("resolved_parent") or query,
                            domain=pj.get("domain"),
                            ticker=pj.get("ticker")
                        )
                    return None
            res = await asyncio.wait_for(_run_intel(), timeout=10.0)
            if res and res.is_brand_or_subsidiary and res.resolved_parent:
                parent_name = res.resolved_parent
                domain = res.domain
                ticker = res.ticker
            else:
                parent_name = query
            logs.append(f"Detection Results -> Target: {parent_name}, Domain: {domain}, Ticker: {ticker}")
        except Exception as e:
            logger.warning(f"Detection LLM failed or timed out: {e}")
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
    
    # Check GLEIF with timeout
    try:
        gleif_res = await asyncio.wait_for(gleif_client.search_lei(target_query), timeout=5.0)
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
            oc_res = await asyncio.wait_for(opencorporates.search_company(target_query), timeout=5.0)
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
        sec_query = ticker if ticker else legal_name
        sec_res = await asyncio.wait_for(sec_client.get_cik_by_name_or_ticker(sec_query), timeout=5.0)
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
        async def _fetch_aliases():
            ddg = DuckDuckGoSearchRun()
            search_text = await asyncio.to_thread(ddg.run, f"{legal_name} former names aliases trading as")
            llm = get_llm(capability="entity_resolution")
            raw_p = (
                "Extract former names and trading aliases as a JSON object with keys 'aliases' (list of strings) and 'historical_names' (list of strings).\n"
                f"Company: {legal_name}\nContext:\n{search_text[:2000]}\nJSON:"
            )
            raw_res = await llm.ainvoke(raw_p)
            raw_text = raw_res.content if hasattr(raw_res, 'content') else str(raw_res)
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if match:
                pj = json.loads(match.group(0))
                return pj.get("aliases", []), pj.get("historical_names", [])
            return [], []

        aliases, historical = await asyncio.wait_for(_fetch_aliases(), timeout=8.0)
        if len(aliases) > 0 or len(historical) > 0:
            logs.append(f"Extracted {len(aliases)} aliases and {len(historical)} historical names.")
    except Exception as e:
        logger.warning(f"Alias expansion failed or timed out: {e}")

    is_sec = bool(cik)
    jurisdiction = country if country and country != "Unknown" else "US"

    # Stage 7: Verification Scoring & Search Planning
    score = 0
    evidence_sources = []
    
    if domain:
        score += 30
        evidence_sources.append("Official Website")
    if reg_number:
        score += 30
        evidence_sources.append("Government Registry")
    if cik:
        score += 25
        evidence_sources.append("SEC EDGAR")
    if lei:
        score += 20
        evidence_sources.append("GLEIF")
    if ticker:
        score += 15
        evidence_sources.append("Stock Ticker")
    if len(aliases) > 0 or len(historical) > 0:
        score += 5
        evidence_sources.append("Wikipedia")
        
    score = min(score, 100)
    
    if score >= 70:
        verification_status = "Verified"
    elif score >= 50:
        verification_status = "Needs Review"
    else:
        verification_status = "Failed"
        
    if verification_status == "Failed":
        logs.append(f"Verification failed. Confidence Score: {score}/100. Parent company could not be verified from authoritative sources.")
        return {
            **state,
            "company_info": {
                "status": "failed",
                "error": "Parent company could not be verified from authoritative sources.",
                "original_query": query,
                "confidence_score": score,
                "evidence_sources": evidence_sources
            },
            "logs": logs
        }

    resolved = ResolvedEntity(
        query_used=query,
        canonical_company=parent_name if parent_name else legal_name,
        official_domain=domain or "",
        country=country,
        legal_name=legal_name,
        registration_number=reg_number,
        cik=cik,
        ticker=ticker,
        is_sec_registered=is_sec,
        primary_jurisdiction=jurisdiction,
        aliases=aliases,
        historical_names=historical,
        parent_company=parent_name if parent_name and parent_name != legal_name else None,
        confidence=score / 100.0
    )
    
    # Generate the fallback plan
    resolved.search_plan = generate_search_plan(resolved, query)
    
    company_info = {
        "legal_name": resolved.legal_name,
        "canonical_company": resolved.canonical_company,
        "official_domain": resolved.official_domain,
        "country": resolved.country,
        "registration_number": resolved.registration_number,
        "cik": resolved.cik,
        "ticker": resolved.ticker,
        "is_sec_registered": resolved.is_sec_registered,
        "primary_jurisdiction": resolved.primary_jurisdiction,
        "aliases": resolved.aliases,
        "historical_names": resolved.historical_names,
        "parent_company": resolved.parent_company,
        "search_plan": resolved.search_plan,
        "original_query": query,
        "confidence": resolved.confidence,
        "confidence_score": score,
        "verification_status": verification_status,
        "evidence_sources": evidence_sources,
        "status": "success"
    }
    
    # Stage 8: Cache Saving
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
