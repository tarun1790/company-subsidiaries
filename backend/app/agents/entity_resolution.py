import json
from pydantic import BaseModel, Field
from typing import Optional
from app.agents.state import AgentState
from app.agents.llm import get_llm
from app.services.sec_edgar_client import sec_client
from app.core.logging import logger
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import DuckDuckGoSearchRun

class ResolvedEntity(BaseModel):
    legal_name: str = Field(description="Official legal corporate name of the company.")
    ticker: Optional[str] = Field(None, description="Stock ticker symbol (e.g. MSFT), if publicly traded.")
    cik: Optional[str] = Field(None, description="SEC Central Index Key (10-digit string), if available.")
    domain: Optional[str] = Field(None, description="Primary web domain (e.g. microsoft.com).")
    hq_country: Optional[str] = Field(None, description="Headquarters country.")
    parent_company: Optional[str] = Field(None, description="Ultimate parent company name, if this entity is a subsidiary itself.")
    confidence: float = Field(description="Confidence score (0.0 to 1.0) of this resolution.")

async def entity_resolution_agent(state: AgentState) -> AgentState:
    """Agent 1: Resolves user search term into a structured corporate profile."""
    query = state["query"]
    logs = state.get("logs", [])
    logs.append(f"Resolving Company: '{query}'...")
    logger.info(f"Running Entity Resolution Agent for: {query}")

    # Fallback search tools
    search_tool = DuckDuckGoSearchRun()
    
    # 1. Gather context from web search
    search_context = ""
    try:
        search_query = f"corporate structure legal name ticker CIK domain headquarter ultimate parent of {query}"
        search_context = search_tool.run(search_query)
    except Exception as e:
        logger.warning(f"Search tool error during entity resolution: {str(e)}")

    # 2. Lookup CIK from SEC Client (for high-confidence filings link)
    cik_lookup = await sec_client.get_cik_by_name_or_ticker(query)
    
    # 3. LLM structured resolution
    llm = get_llm()
    structured_llm = llm.with_structured_output(ResolvedEntity)

    system_prompt = (
        "You are an expert corporate intelligence analyst.\n"
        "Your task is to resolve the user's search query (which may be a name, ticker, or domain) "
        "into a structured corporate metadata profile. Use the provided search context and SEC CIK lookup.\n"
        "Be highly accurate and do not hallucinate."
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Query: {query}\n\nSEC CIK Lookup Result: {cik_lookup}\n\nSearch Context:\n{context}")
    ])

    resolved = None
    try:
        chain = prompt | structured_llm
        resolved = await chain.ainvoke({
            "query": query,
            "cik_lookup": cik_lookup or "Not found",
            "context": search_context
        })
    except Exception as e:
        logger.error(f"Entity Resolution Agent LLM parsing failed: {str(e)}")
        # Graceful fallback in case of LLM failure
        resolved = ResolvedEntity(
            legal_name=query,
            cik=cik_lookup,
            confidence=0.5
        )

    # Overwrite CIK if it was resolved by client but missed by LLM
    if cik_lookup and not resolved.cik:
        resolved.cik = cik_lookup

    company_info = resolved.dict()
    logs.append(f"Resolved to legal name: '{resolved.legal_name}' (Confidence: {resolved.confidence * 100:.0f}%)")
    
    return {
        **state,
        "company_info": company_info,
        "logs": logs
    }
