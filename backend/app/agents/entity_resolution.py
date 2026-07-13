import json
import asyncio
import re
import httpx
import socket
import whois
import dns.resolver
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.agents.state import AgentState
from app.agents.llm import get_llm
from app.services.sec_edgar_client import sec_client
from app.core.logging import logger
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import DuckDuckGoSearchRun

# ============================================================================
# Pydantic Schemas for Multi-Source Reconciliation
# ============================================================================

class CandidateEntity(BaseModel):
    source: str = Field(description="Name of the source supplying this candidate (e.g. SEC EDGAR, WHOIS, Wikipedia, DDG Search).")
    legal_name: str = Field(description="Exact legal name found in this source.")
    domain: Optional[str] = Field(None, description="Primary domain of the entity.")
    cik: Optional[str] = Field(None, description="SEC CIK (10-digit) if found in this source.")
    ticker: Optional[str] = Field(None, description="Stock ticker if found in this source.")
    hq_country: Optional[str] = Field(None, description="Headquarters country found in this source.")
    parent_company: Optional[str] = Field(None, description="Ultimate parent entity if specified in this source.")
    confidence_score: float = Field(description="Confidence score (0.0 to 1.0) of this candidate based on source accuracy.")

class ConsensusEntity(BaseModel):
    legal_name: str = Field(description="The reconciled legal corporate name.")
    domain: Optional[str] = Field(None, description="Reconciled primary domain.")
    cik: Optional[str] = Field(None, description="Reconciled SEC CIK (10-digit).")
    ticker: Optional[str] = Field(None, description="Reconciled stock ticker.")
    hq_country: Optional[str] = Field(None, description="Reconciled headquarters country.")
    parent_company: Optional[str] = Field(None, description="Reconciled parent company if applicable.")
    confidence: float = Field(description="Overall consensus confidence score (0.0 to 1.0) based on source agreement.")

class ResolutionResult(BaseModel):
    candidates: List[CandidateEntity] = Field(description="List of candidates identified from each source.")
    is_ambiguous: bool = Field(description="Set to True if sources disagree on key fields (different legal names, CIKs, domains) and no clear consensus can be established.")
    consensus: Optional[ConsensusEntity] = Field(None, description="The final consensus entity. Must be None if is_ambiguous is True.")
    explanation: str = Field(description="Detailed reconciliation explanation of agreements, disagreements, or lack of evidence.")

# ============================================================================
# Helper Gatherers for Live Sources
# ============================================================================

def is_domain(query: str) -> bool:
    return "." in query and " " not in query

async def gather_whois_dns(domain: str) -> str:
    res = []
    # 1. DNS A record lookup
    try:
        answers = await asyncio.to_thread(dns.resolver.resolve, domain, 'A')
        ips = [str(rdata) for rdata in answers]
        res.append(f"DNS A Records: {', '.join(ips)}")
    except Exception as e:
        res.append(f"DNS Lookup error: {str(e)}")
        
    # 2. WHOIS registry lookup
    try:
        w = await asyncio.to_thread(whois.whois, domain)
        res.append(f"Registrar: {w.registrar}")
        res.append(f"Registrant Org: {w.org or w.get('organization')}")
        res.append(f"Registrant Country: {w.country}")
        if w.creation_date:
            dates = w.creation_date if isinstance(w.creation_date, list) else [w.creation_date]
            res.append(f"Creation Date: {dates[0].isoformat() if hasattr(dates[0], 'isoformat') else str(dates[0])}")
    except Exception as e:
        res.append(f"WHOIS lookup error: {str(e)}")
        
    return "\n".join(res)

async def gather_crt_sh(domain: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"https://crt.sh/?q={domain}&output=json")
            if response.status_code == 200:
                data = response.json()
                names = sorted(list(set(item["common_name"] for item in data[:20])))
                return "Certificate Transparency Logs:\n- " + "\n- ".join(names[:8])
    except Exception as e:
        return f"Certificate Transparency lookup error: {str(e)}"
    return "No Certificate Transparency logs found."

# ============================================================================
# Agent Main Logic
# ============================================================================

async def entity_resolution_agent(state: AgentState) -> AgentState:
    """Agent 1: Resolves user search term into a verified legal entity using multi-source consensus."""
    query = state["query"].strip()
    logs = state.get("logs", [])
    logs.append(f"Resolving Company Entity: '{query}'...")
    logger.info(f"Initiating entity resolution consensus for query: {query}")

    # Initialize tools
    search_tool = DuckDuckGoSearchRun()

    # Define parallel gathering tasks
    async def get_sec():
        try:
            return await sec_client.get_cik_by_name_or_ticker(query)
        except Exception as e:
            return f"SEC lookup failed: {str(e)}"

    async def get_web_search():
        try:
            q = f"corporate legal entity name ticker CIK domain headquarter parent company of {query}"
            return await asyncio.to_thread(search_tool.run, q)
        except Exception as e:
            return f"Web search failed: {str(e)}"

    async def get_wiki_search():
        try:
            q = f"site:en.wikipedia.org legal name headquarters parent company of {query}"
            return await asyncio.to_thread(search_tool.run, q)
        except Exception as e:
            return f"Wikipedia search failed: {str(e)}"

    # Run parallel gather tasks
    sec_task = get_sec()
    web_task = get_web_search()
    wiki_task = get_wiki_search()

    whois_task = None
    crt_task = None
    if is_domain(query):
        whois_task = gather_whois_dns(query)
        crt_task = gather_crt_sh(query)
    else:
        # If it's a query like Alphabet, let's extract a domain candidate first via quick search
        try:
            domain_query = f"official website domain address of {query}"
            domain_search = await asyncio.to_thread(search_tool.run, domain_query)
            urls = re.findall(r'https?://(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,6})', domain_search)
            if urls:
                domain_candidate = urls[0]
                logger.info(f"Discovered candidate domain for WHOIS/DNS: {domain_candidate}")
                whois_task = gather_whois_dns(domain_candidate)
                crt_task = gather_crt_sh(domain_candidate)
        except Exception:
            pass

    # Await all gathering tasks
    tasks = [sec_task, web_task, wiki_task]
    if whois_task:
        tasks.append(whois_task)
    if crt_task:
        tasks.append(crt_task)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    sec_res = results[0]
    web_res = results[1]
    wiki_res = results[2]
    whois_res = results[3] if len(results) > 3 else "N/A"
    crt_res = results[4] if len(results) > 4 else "N/A"

    # Format evidence payload
    evidence_text = (
        f"--- SEC EDGAR Registry Lookup ---\n{sec_res}\n\n"
        f"--- DuckDuckGo Corporate Search ---\n{web_res}\n\n"
        f"--- Wikipedia Registry Search ---\n{wiki_res}\n\n"
        f"--- DNS & WHOIS Registry Record ---\n{whois_res}\n\n"
        f"--- Certificate Transparency Logs ---\n{crt_res}\n"
    )

    # Invoke LLM for structured reconciliation
    llm = get_llm()
    structured_llm = llm.with_structured_output(ResolutionResult)

    system_prompt = (
        "You are a strict, expert corporate intelligence reconciliation manager.\n"
        "Your task is to analyze raw evidence gathered from multiple independent registries and tools, "
        "reconcile candidates, and determine if consensus can be reached.\n\n"
        "Strict Reconcilation & Validation Rules:\n"
        "1. Identify the candidate entity from each source separately.\n"
        "2. Compare the Legal Name, Domain, CIK, Ticker, HQ Country, and Parent Company of the candidates.\n"
        "3. If these fields disagree across sources (e.g. different headquarters, different ultimate parent corporate groups), "
        "or if there is no strong consensus, set is_ambiguous = True and consensus = null.\n"
        "4. NEVER invent or guess names, domains, or registries. All values must strictly derive from the text evidence.\n"
        "5. If there is insufficient evidence or the sources are unclear, set is_ambiguous = True and consensus = null.\n"
        "6. Do not default or fall back to preset companies. Treat all inputs dynamically."
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Query: {query}\n\nRaw Evidence Collected:\n{evidence}")
    ])

    resolved = None
    try:
        chain = prompt | structured_llm
        resolved = await chain.ainvoke({
            "query": query,
            "evidence": evidence_text
        })
    except Exception as e:
        logger.error(f"Resolution LLM reconciliation execution error: {str(e)}")
        resolved = ResolutionResult(
            candidates=[],
            is_ambiguous=True,
            consensus=None,
            explanation=f"LLM agent failed to reconcile candidates due to error: {str(e)}"
        )

    # Process failure or success policy
    if resolved.is_ambiguous or not resolved.consensus or resolved.consensus.confidence < 0.7:
        error_msg = (
            "Unable to confidently resolve the requested company. "
            "Please provide additional information such as the official website, country, or stock ticker."
        )
        logs.append(f"Resolution Failed: {resolved.explanation}")
        return {
            **state,
            "company_info": {
                "status": "failed",
                "error": error_msg,
                "explanation": resolved.explanation
            },
            "logs": logs,
            "errors": state.get("errors", []) + [error_msg]
        }

    # Successful resolution
    consensus = resolved.consensus
    company_info = {
        "status": "success",
        "legal_name": consensus.legal_name,
        "domain": consensus.domain,
        "cik": consensus.cik,
        "ticker": consensus.ticker,
        "hq_country": consensus.hq_country,
        "parent_company": consensus.parent_company,
        "confidence": consensus.confidence,
        "metadata_fields": {
            "explanation": resolved.explanation,
            "resolved_candidates": [c.dict() for c in resolved.candidates]
        }
    }

    logs.append(f"Successfully resolved entity: '{consensus.legal_name}' (Confidence: {consensus.confidence * 100:.0f}%)")
    logger.info(f"Reconciled entity consensus reached: {consensus.legal_name}")

    return {
        **state,
        "company_info": company_info,
        "logs": logs
    }
