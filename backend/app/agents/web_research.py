from pydantic import BaseModel, Field
from typing import List, Optional
from app.agents.state import AgentState
from app.agents.llm import get_llm
from app.services.dns_whois import resolver
from app.core.logging import logger
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import DuckDuckGoSearchRun, DuckDuckGoSearchResults, WikipediaQueryRun
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
    """Agent 5: Conducts Wikipedia, certificate transparency, and general search queries to discover acquisitions/brands."""
    company_info = state["company_info"]
    subsidiaries = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    errors = state.get("errors", [])
    
    legal_name = company_info.get("legal_name") or state["query"]
    domain = company_info.get("domain")
    
    logs.append("Running Web Research Agent (Wikipedia, SSL Certificates, Web Search)...")
    logger.info(f"Web Research Agent searching for: {legal_name}")

    discovered = []
    search_context = ""
    
    # 1. Search Wikipedia (LangChain Community Tool)
    try:
        logs.append("Invoking LangChain Tool: langchain_community.tools.WikipediaQueryRun...")
        wiki = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
        wiki_res = wiki.run(f"{legal_name} corporate subsidiaries acquisitions history")
        if wiki_res and "No good Wikipedia page found" not in wiki_res:
            search_context += f"--- WIKIPEDIA ENTRY ---\n{wiki_res}\n\n"
    except Exception as e:
        logger.warning(f"Wikipedia search error: {str(e)}")

    # 2. Query crt.sh (Certificate Transparency) for related domains if domain is available
    if domain:
        try:
            logs.append(f"Searching SSL Certificate Transparency logs for {domain}...")
            domains = await resolver.get_cert_transparency_domains(domain)
            if domains:
                domains_summary = ", ".join(domains[:15]) # top 15 domains
                search_context += f"--- CERTIFICATE TRANSPARENCY DOMAINS ---\nAssociated domains detected: {domains_summary}\n\n"
        except Exception as e:
            logger.warning(f"Cert transparency lookup error: {str(e)}")

    # 3. DuckDuckGo Search (LangChain Community Tools)
    try:
        logs.append("Invoking LangChain Tool: langchain_community.tools.DuckDuckGoSearchRun...")
        ddg = DuckDuckGoSearchRun()
        ddg_res = ddg.run(f"{legal_name} list of subsidiaries divisions brands joint ventures")
        search_context += f"--- WEB SEARCH RESULTS ---\n{ddg_res}\n\n"
        
        logs.append("Invoking LangChain Tool: langchain_community.tools.DuckDuckGoSearchResults...")
        ddg_results = DuckDuckGoSearchResults()
        ddg_links_res = ddg_results.run(f"{legal_name} corporate structure")
        search_context += f"--- WEB LINK SCHEMAS ---\n{ddg_links_res}\n\n"
    except Exception as e:
        logger.warning(f"DDG search error: {str(e)}")

    # 4. LLM Extraction
    if len(search_context.strip()) > 100:
        try:
            llm = get_llm()
            structured_llm = llm.with_structured_output(WebResearchOutput)
            
            system_prompt = (
                "You are an elite corporate intelligence officer.\n"
                "Given the consolidated research context (Wikipedia, SSL certificates, Web search), "
                "extract every verified subsidiary, acquisition, division, brand, or regional entity associated with the primary company.\n"
                "Provide their name, country, relationship type, a direct supporting quote, and source citation.\n"
                "Be extremely careful. Do not extract customers, suppliers, unrelated partner companies, or competitors."
            )
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", "Primary Company: {company}\n\nResearch Context:\n{context}")
            ])
            
            chain = prompt | structured_llm
            result = await chain.ainvoke({
                "company": legal_name,
                "context": search_context[:25000] # Limit context size
            })
            
            for entity in result.entities:
                discovered.append({
                    "name": entity.name,
                    "legal_name": entity.name,
                    "country": entity.country,
                    "ownership": entity.ownership or "Not Publicly Disclosed",
                    "parent": legal_name,
                    "relationship_type": entity.relationship_type,
                    "confidence": 0.65 if "wikipedia" in entity.source_citation.lower() else 0.50,
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
        "logs": logs
    }
