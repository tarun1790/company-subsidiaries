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

class CorporateGroupEntity(BaseModel):
    legal_name: str = Field(description="Name of the related entity within the corporate group.")
    entity_type: str = Field(description="Classification: Public Company, Private Company, Brand, Product, Subsidiary, Business Unit, Regional Entity, Domain, Stock Ticker.")
    relationship: str = Field(description="Relationship to the canonical company (e.g., Parent of, Subsidiary of, Operating name of, Brand of, Product of, Business Unit of).")

class ConsensusEntity(BaseModel):
    legal_name: str = Field(description="The reconciled legal corporate name.")
    entity_classification: str = Field(description="Classification: Public Company, Private Company, Brand, Product, Subsidiary, Business Unit, Regional Entity, Domain, Stock Ticker.")
    domain: Optional[str] = Field(None, description="Reconciled primary domain.")
    cik: Optional[str] = Field(None, description="Reconciled SEC CIK (10-digit).")
    ticker: Optional[str] = Field(None, description="Reconciled stock ticker.")
    hq_country: Optional[str] = Field(None, description="Reconciled headquarters country.")
    
    # Parent resolution mappings
    immediate_parent: Optional[str] = Field(None, description="Immediate parent company resolved (especially if query is a Brand, Product, Business Unit, or Subsidiary).")
    ultimate_parent: Optional[str] = Field(None, description="Ultimate parent company resolved (especially if query is a Brand, Product, Business Unit, or Subsidiary).")
    
    confidence: float = Field(description="Overall consensus confidence score (0.0 to 1.0) based on source agreement.")
    corporate_group_entities: List[CorporateGroupEntity] = Field(default=[], description="Other verified entities belonging to this corporate group resolved in the query context.")

class ResolutionResult(BaseModel):
    candidates: List[CandidateEntity] = Field(description="List of candidates identified from each source.")
    is_ambiguous: bool = Field(description="Set to True if authoritative sources actively conflict on the ultimate parent entity and the conflict cannot be resolved.")
    consensus: Optional[ConsensusEntity] = Field(None, description="The final consensus entity. Must be None if is_ambiguous is True.")
    explanation: str = Field(description="Detailed reconciliation explanation of agreements, disagreements, or lack of evidence.")

# ============================================================================
# Helper Gatherers for Live Sources
# ============================================================================

def is_domain(query: str) -> bool:
    return "." in query and " " not in query

WHOIS_PRIVACY_PROXIES = {
    "perfect privacy", "whoisguard", "domains by proxy", "privacy protect", 
    "redacted for privacy", "registrant privacy", "identity protect", "contact privacy", 
    "super privacy", "whois privacy", "privacy service", "withheld for privacy", 
    "privacyprotect", "domain privacy", "select privacy"
}

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
        org = str(w.org or w.get('organization') or "")
        org_clean = org.strip()
        if any(proxy in org_clean.lower() for proxy in WHOIS_PRIVACY_PROXIES):
            org_clean = "Privacy Guard Proxy (Discarded)"
            
        res.append(f"Registrar: {w.registrar}")
        res.append(f"Registrant Org: {org_clean}")
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

# ============================================================================
# Helper domain parser and normalizer
# ============================================================================

def normalize_and_get_domain(url_or_name: str) -> Optional[str]:
    """Clean and normalize URL or name to extract the apex/root domain."""
    s = url_or_name.strip().lower()
    
    # Check if there is a dot indicating a domain/URL
    if not re.search(r'[a-zA-Z0-9-]+\.[a-zA-Z]{2,6}', s):
        return None
        
    s = re.sub(r'^https?://', '', s)
    s = re.sub(r'^[^/]+@', '', s)
    s = re.sub(r':[0-9]+', '', s)
    
    # Strip paths, queries, fragments
    s = s.split('/')[0].split('?')[0].split('#')[0]
    s = re.sub(r'^www\.', '', s)
    
    parts = s.split('.')
    if len(parts) >= 3:
        double_tlds = {"co", "com", "org", "net", "gov", "edu", "ac", "or", "ne", "me"}
        if parts[-2] in double_tlds and len(parts[-1]) == 2:
            return ".".join(parts[-3:])
        return ".".join(parts[-2:])
    elif len(parts) == 2:
        return s
    return s

def find_domain_in_text(text: str, query: str = None) -> Optional[str]:
    """Helper to robustly extract a corporate domain from search result text matching the query."""
    if not text:
        return None
    excludes = {
        "wikipedia.org", "duckduckgo.com", "google.com", "brave.com", 
        "yandex.com", "yahoo.com", "startpage.com", "grokipedia.com",
        "w3.org", "sec.gov", "gleif.org", "opencorporates.com"
    }
    valid_tlds = {
        "com", "org", "net", "mil", "edu", "gov", "co", "io", "info", "biz", "us", "uk", "ca", "de", "jp", "fr", "au",
        "in", "cn", "ru", "es", "it", "nl", "se", "no", "fi", "dk", "ch", "at", "be", "pl", "br", "mx", "za", "sg", "hk",
        "tw", "kr", "my", "id", "th", "vn", "ph", "tr", "sa", "ae", "il", "gr", "pt", "ie", "nz", "cl", "ar", "coop", "mobi",
        "travel", "museum", "jobs", "post", "asia", "cat", "tel", "xxx", "pro", "me", "tv", "cc", "fm", "am", "vc", "bz",
        "ws", "la", "to", "ms", "tc", "vg", "gd", "cx", "tl", "sh", "ac", "io", "app", "dev", "ai", "tech", "online", "site",
        "store", "blog", "xyz", "club", "space", "website", "ltd", "gmbh", "company", "agency", "solutions", "services",
        "global", "world"
    }
    
    candidates = []
    # 1. Search for full URLs
    urls = re.findall(r'https?://(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,6})', text)
    for u in urls:
        u_clean = u.lower().strip()
        tld = u_clean.split('.')[-1]
        if tld in valid_tlds and not any(ex in u_clean for ex in excludes):
            if u_clean not in candidates:
                candidates.append(u_clean)
                
    # 2. Search for any word containing dot and valid TLD
    words = re.findall(r'\b([a-zA-Z0-9-]+\.[a-zA-Z]{2,6})\b', text)
    for w in words:
        w_clean = w.lower().strip()
        tld = w_clean.split('.')[-1]
        if tld in valid_tlds and not any(ex in w_clean for ex in excludes):
            if not re.match(r'^[0-9\.]+$', w_clean):
                if w_clean not in candidates:
                    candidates.append(w_clean)
                    
    if not candidates:
        if query:
            clean_q = re.sub(r'[^\w]', '', query.lower()).strip()
            if len(clean_q) >= 3:
                return f"{clean_q}.com"
        return None
        
    # If query is provided, score candidates by overlap with query
    if query:
        query_words = re.sub(r'[^\w\s]', ' ', query.lower()).split()
        query_words = [qw for qw in query_words if len(qw) >= 3 and qw not in ["official", "corporate", "website", "domain", "address"]]
        
        best_candidate = None
        best_score = -1.0
        
        for c in candidates:
            score = 0.0
            for qw in query_words:
                if qw in c:
                    score += 10.0
            # Tie breaker: prefer shorter domains
            score -= len(c) * 0.1
            
            if score > best_score:
                best_score = score
                best_candidate = c
                
        # If we found a candidate with at least one matching query word, return it
        if best_score >= 5.0:
            return best_candidate
            
        # Fallback: if none matched the query, default to query.com if query is sensible
        clean_q = re.sub(r'[^\w]', '', query.lower()).strip()
        if len(clean_q) >= 3:
            for c in candidates:
                if clean_q[:4] in c:
                    return c
            return f"{clean_q}.com"
            
    return candidates[0]

# ============================================================================
# Pydantic Schemas for Structured LLM Extraction & Consensus
# ============================================================================

class CandidateExtraction(BaseModel):
    candidate_names: List[str] = Field(description="Exact legal company name candidates extracted from the website footer, copyright, or WHOIS data.")
    has_footer_legal_entity: bool = Field(description="Set to True if a legal corporate entity name is explicitly found in the copyright or footer text.")
    explanation: str = Field(description="Short rationale for the extracted candidate names.")

class ConsensusEntityResolution(BaseModel):
    canonical_company: str = Field(description="The reconciled canonical legal company name.")
    official_domain: str = Field(description="The canonical domain resolved.")
    country: str = Field(description="The country of registration or headquarters.")
    legal_name: str = Field(description="The full legal name of the canonical entity.")
    registration_number: Optional[str] = Field(None, description="Corporate registration number, CIK, or LEI resolved.")
    explanation: str = Field(description="Explanation of the consensus.")

class InputIntelligence(BaseModel):
    input_type: str = Field(description="Classified input type: COMPANY_NAME, BRAND, DOMAIN, URL, LEGAL_ENTITY, TICKER, APP_NAME.")
    normalized_name: str = Field(description="Normalized name/term.")
    resolved_ultimate_parent: str = Field(description="The ultimate parent company legal name (e.g. Alphabet Inc. for YouTube, Meta Platforms Inc. for Instagram). If the input is already a parent company or standalone company, return its own name.")
    official_website: str = Field(description="The official website domain of the ultimate parent company (e.g. meta.com for Instagram or YouTube). If none can be found, return the best candidate domain.")
    explanation: str = Field(description="Brief reason/evidence linking the input to the resolved ultimate parent company.")

COMMON_BRANDS_FALLBACK = {
    "instagram": ("Meta Platforms, Inc.", "meta.com"),
    "youtube": ("Alphabet Inc.", "google.com"),
    "whatsapp": ("Meta Platforms, Inc.", "meta.com"),
    "gmail": ("Alphabet Inc.", "google.com"),
    "android": ("Alphabet Inc.", "google.com"),
    "aws": ("Amazon.com, Inc.", "amazon.com"),
    "kindle": ("Amazon.com, Inc.", "amazon.com"),
    "github": ("Microsoft Corporation", "microsoft.com"),
    "linkedin": ("Microsoft Corporation", "microsoft.com"),
    "xbox": ("Microsoft Corporation", "microsoft.com"),
    "beats": ("Apple Inc.", "apple.com"),
    "meta": ("Meta Platforms, Inc.", "meta.com"),
    "instagram.com": ("Meta Platforms, Inc.", "meta.com"),
    "youtube.com": ("Alphabet Inc.", "google.com"),
    "whatsapp.com": ("Meta Platforms, Inc.", "meta.com"),
}

# ============================================================================
# Agent Main Logic
# ============================================================================

async def entity_resolution_agent(state: AgentState) -> AgentState:
    """Agent 1: Resolves user search term into a verified legal entity using multi-source consensus."""
    raw_query = state.get("query")
    if isinstance(raw_query, dict):
        query = str(raw_query.get("query") or raw_query.get("company_info", {}).get("legal_name") or "").strip()
    else:
        query = str(raw_query or "").strip()
        
    logs = state.get("logs", [])
    logs.append(f"Initiating Enterprise Entity Resolution for: '{query}'...")
    logger.info(f"Initiating Enterprise Entity Resolution consensus for query: {query}")

    from app.services.dns_whois import resolver
    from app.services.gleif import gleif_client
    from app.services.open_corporates import opencorporates
    from app.services.web_scraper import scraper

    search_tool = DuckDuckGoSearchRun()

    # Step 1: Universal Input Intelligence Layer
    logs.append("Running Universal Input Intelligence Layer...")
    
    query_lower = query.lower().strip()
    parent_name = None
    parent_domain = None
    
    # 1.1 Programmatic brand fallback check
    if query_lower in COMMON_BRANDS_FALLBACK:
        parent_name, parent_domain = COMMON_BRANDS_FALLBACK[query_lower]
        logs.append(f"Input Intelligence: Match brand/app '{query}' -> Parent: '{parent_name}' ({parent_domain})")
    else:
        # 1.2 LLM-driven input intelligence classification
        llm = get_llm(capability="entity_resolution")
        intelligence_llm = llm.with_structured_output(InputIntelligence)
        intel_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are the Universal Input Intelligence analyst.\n"
                "Your job is to analyze the user query (which could be a brand, product, app, subsidiary, ticker, URL, or company) "
                "and resolve it to its ultimate parent corporate legal entity name and its official domain.\n"
                "For example:\n"
                "- 'Instagram' -> parent: 'Meta Platforms, Inc.', domain: 'meta.com'\n"
                "- 'YouTube' -> parent: 'Alphabet Inc.', domain: 'google.com'\n"
                "- 'AWS' -> parent: 'Amazon.com, Inc.', domain: 'amazon.com'\n"
                "- 'NFLX' -> parent: 'Netflix, Inc.', domain: 'netflix.com'\n"
                "- 'Flipkart' -> parent: 'Walmart Inc.' (or 'Flipkart Private Limited' if resolving standalone corporate structure)\n"
                "If the query is already an independent parent company, return its own name and domain."
            )),
            ("user", "User Query: {query}")
        ])
        
        try:
            intel_chain = intel_prompt | intelligence_llm
            result = await intel_chain.ainvoke({"query": query})
            parent_name = result.resolved_ultimate_parent
            parent_domain = result.official_website
            logs.append(f"Input Intelligence resolved input type '{result.input_type}' to ultimate parent: '{parent_name}' ({parent_domain})")
        except Exception as intel_err:
            logger.warning(f"Input Intelligence LLM failed: {str(intel_err)}")
            # Fall back to standard search-based lookup
            parent_name = query
            parent_domain = normalize_and_get_domain(query)
            if not parent_domain:
                try:
                    logs.append("Searching web for official corporate domain...")
                    domain_query = f"official corporate website domain address of {query}"
                    domain_search = await asyncio.to_thread(search_tool.run, domain_query)
                    parent_domain = find_domain_in_text(domain_search, query)
                except Exception as se:
                    logger.debug(f"Domain search failed: {str(se)}")

    domain = normalize_and_get_domain(parent_domain) if parent_domain else None
    if parent_name and parent_name != query:
        # Override target query with resolved parent name to search parent records downstream
        logs.append(f"Switching resolution target from '{query}' to resolved parent '{parent_name}' ({domain or 'No Domain'})")
        # Update state query so downstream collectors target the resolved parent
        state["query"] = parent_name

    # Step 2 & 3: Visit domain to scrape text and extract candidates
    web_text = ""
    title = ""
    meta_desc = ""
    if domain:
        logs.append(f"Visiting official website: {domain}...")
        # Resolve canonical URL first via fast redirect lookup
        canonical_url = f"https://{domain}"
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                resp = await client.get(f"https://{domain}")
                canonical_url = str(resp.url)
        except Exception:
            try:
                async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                    resp = await client.get(f"https://www.{domain}")
                    canonical_url = str(resp.url)
            except Exception:
                pass
                
        logs.append(f"Scraping canonical URL: {canonical_url}...")
        try:
            scraped = await scraper.scrape_url(canonical_url)
            if scraped:
                web_text = scraped
        except Exception as scraper_err:
            logger.debug(f"Scraper failed for {canonical_url}: {str(scraper_err)}")

    # Step 4: Validate using WHOIS, DNS, SSL
    whois_info = {}
    dns_records = {}
    ssl_domains = []
    if domain:
        logs.append("Fetching DNS, WHOIS, and Certificate Transparency records...")
        whois_info = await resolver.get_whois_info(domain)
        dns_records = await resolver.get_dns_records(domain)
        ssl_domains = await resolver.get_cert_transparency_domains(domain)

    # Use LLM to extract candidates and footer information
    llm = get_llm(capability="entity_resolution")
    candidate_llm = llm.with_structured_output(CandidateExtraction)

    extract_prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are an enterprise entity resolution analyst.\n"
            "Analyze the website text and WHOIS registrant data below.\n"
            "Extract any exact corporate legal entity names (e.g. containing Inc, LLC, Ltd, Private Limited, GmbH, Corp).\n"
            "Determine if a valid legal company name is explicitly declared in the copyright notice or footer text."
        )),
        ("user", "Website Text:\n{web_text}\n\nWHOIS Registrant Org: {whois_org}")
    ])

    whois_org = whois_info.get("org") or "N/A"
    extraction = None
    try:
        extract_chain = extract_prompt | candidate_llm
        extraction = await extract_chain.ainvoke({
            "web_text": web_text[:8000] if web_text else "No website content scraped.",
            "whois_org": whois_org
        })
    except Exception as ee:
        logger.warning(f"Failed to extract candidates using LLM: {str(ee)}")
        # Programmatic fallback candidate extraction
        candidate_names = []
        if whois_org and whois_org != "N/A" and not whois_org.startswith("http") and "." not in whois_org:
            candidate_names.append(whois_org)
        if domain:
            base_name = domain.split('.')[0].capitalize()
            base_clean = base_name.lower().strip()
            suffixes = {"inc", "llc", "ltd", "corp", "co", "plc", "gmbh", "ag", "sa", "bv", "nv", "sarl", "as", "pvt", "private", "limited", "company"}
            if base_clean not in suffixes and len(base_clean) >= 3:
                if base_name not in candidate_names:
                    candidate_names.append(base_name)
        if not candidate_names:
            candidate_names.append(query)
            
        has_footer_legal = False
        if web_text:
            for name in candidate_names:
                if len(name) > 3 and name.lower() in web_text.lower():
                    has_footer_legal = True
                    break
                    
        extraction = CandidateExtraction(
            candidate_names=candidate_names,
            has_footer_legal_entity=has_footer_legal,
            explanation=f"LLM extraction failure: {str(ee)}"
        )

    # Step 5: Search Regulatory registries for candidates
    registry_matches = []
    sec_matches = []
    
    # Build list of names to search (parent name, original query, and scraped candidates)
    search_names = []
    if parent_name:
        search_names.append(parent_name)
    if query and query not in search_names:
        search_names.append(query)
    for name in extraction.candidate_names:
        if name and name not in search_names:
            search_names.append(name)
            
    # Deduplicate search names while preserving order
    seen = set()
    search_names = [x for x in search_names if not (x.lower() in seen or seen.add(x.lower()))]
    
    # Query registries for the top candidates
    for name in search_names[:3]:
        if not name or name.lower() in ["not found", "n/a", "private", "redacted"]:
            continue
            
        # 1. SEC CIK search
        try:
            sec_res = await sec_client.get_cik_by_name_or_ticker(name)
            if sec_res and sec_res != "Not found" and not str(sec_res).startswith("SEC lookup failed"):
                sec_matches.append({"name": name, "cik": sec_res})
        except Exception:
            pass
            
        # 2. GLEIF lookup
        try:
            gleif_res = await gleif_client.search_lei(name)
            if gleif_res:
                registry_matches.extend(gleif_res)
        except Exception:
            pass
            
        # 3. OpenCorporates / Companies House lookup
        try:
            oc_res = await opencorporates.search_company(name)
            if oc_res:
                registry_matches.extend(oc_res)
        except Exception:
            pass

    # Step 6: Resolve Canonical Consensus Entity using LLM
    consensus_llm = llm.with_structured_output(ConsensusEntityResolution)

    consensus_prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are an enterprise corporate entity resolution manager.\n"
            "Review the scraped candidates, WHOIS data, and regulatory matches below.\n"
            "Resolve the absolute canonical legal corporate entity name and its country of registration.\n"
            "Do NOT guess or invent fields."
        )),
        ("user", (
            "User Query: {query}\n"
            "Official Domain: {domain}\n"
            "Extracted Footer Candidates: {candidates}\n"
            "WHOIS Org: {whois_org}\n"
            "Regulatory Matches: {registry_matches}\n"
            "SEC Matches: {sec_matches}"
        ))
    ])

    resolved = None
    try:
        consensus_chain = consensus_prompt | consensus_llm
        resolved = await consensus_chain.ainvoke({
            "query": parent_name or query,
            "domain": domain or "N/A",
            "candidates": ", ".join(extraction.candidate_names),
            "whois_org": whois_org,
            "registry_matches": json.dumps(registry_matches[:5]),
            "sec_matches": json.dumps(sec_matches)
        })
    except Exception as ce:
        logger.error(f"LLM Consensus failed: {str(ce)}")
        # Programmatic consensus fallback
        canonical = extraction.candidate_names[0]
        if sec_matches:
            canonical = sec_matches[0]["name"]
        elif registry_matches:
            canonical = registry_matches[0]["name"]
            
        resolved = ConsensusEntityResolution(
            canonical_company=canonical,
            official_domain=domain or "",
            country="United States" if sec_matches else (registry_matches[0].get("country", "Global") if registry_matches else "Global"),
            legal_name=canonical,
            registration_number=sec_matches[0]["cik"] if sec_matches else (registry_matches[0]["registration_number"] if registry_matches else None),
            explanation=f"Consensus fallback: {str(ce)}"
        )

    # Step 7: Compute Entity Resolution Confidence Score
    has_footer = extraction.has_footer_legal_entity
    has_registry = len(registry_matches) > 0 or len(sec_matches) > 0
    has_whois = False
    if whois_org and whois_org.lower() not in ["not found", "n/a", "private", "redacted"]:
        for candidate in extraction.candidate_names:
            if whois_org.lower() in candidate.lower() or candidate.lower() in whois_org.lower():
                has_whois = True
                break
                
    has_dns = len(dns_records.get("A", [])) > 0 or len(dns_records.get("MX", [])) > 0
    has_ssl = len(ssl_domains) > 0
    has_search = True
    has_consensus = True

    confidence_score = 0
    if has_footer: confidence_score += 40
    if has_registry: confidence_score += 30
    if has_whois: confidence_score += 10
    if has_dns: confidence_score += 5
    if has_ssl: confidence_score += 5
    if has_search: confidence_score += 5
    if has_consensus: confidence_score += 5

    logs.append(f"Entity Resolution confidence score computed: {confidence_score}%")

    company_info = {
        "canonical_company": resolved.canonical_company,
        "official_domain": resolved.official_domain or domain or "",
        "domain": resolved.official_domain or domain or "",
        "country": resolved.country,
        "hq_country": resolved.country,
        "legal_name": resolved.legal_name,
        "registration_number": resolved.registration_number or (registry_matches[0]["registration_number"] if registry_matches else None),
        "confidence": float(confidence_score) / 100.0,
        "cik": sec_matches[0]["cik"] if sec_matches else None,
        "entity_classification": "Public Company" if sec_matches else "Private Company",
        "original_query": query,
        "metadata_fields": {
            "explanation": resolved.explanation,
            "resolved_candidates": registry_matches + sec_matches,
            "corporate_group_entities": []
        }
    }

    # Determine success or failure based on whether we have a resolved company name
    resolved_name = resolved.canonical_company or resolved.legal_name or ""
    resolved_clean = re.sub(r'[^\w\s]', '', resolved_name).strip().lower()
    suffixes = {"inc", "llc", "ltd", "corp", "co", "plc", "gmbh", "ag", "sa", "bv", "nv", "sarl", "as", "pvt", "private", "limited", "company"}
    
    has_resolved_entity = bool(resolved_name) and resolved_clean not in suffixes and len(resolved_clean) >= 3
    
    if has_resolved_entity:
        company_info["status"] = "success"
        logs.append(f"Successfully resolved entity: '{resolved.canonical_company}' (Confidence: {confidence_score}%)")
        return {
            **state,
            "company_info": company_info,
            "logs": logs
        }
    else:
        error_msg = (
            "Unable to resolve the requested company. No legal entity name or domain could be verified "
            "from public registries, website content, or search engines. Please clarify by providing "
            "the official website address or exact legal name."
        )
        company_info["status"] = "failed"
        company_info["error"] = error_msg
        logs.append("Resolution failed: No canonical company resolved. Requesting user clarification.")
        return {
            **state,
            "company_info": company_info,
            "logs": logs,
            "errors": state.get("errors", []) + [error_msg]
        }
