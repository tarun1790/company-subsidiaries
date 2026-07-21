import re
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.agents.state import AgentState
from app.agents.llm import get_llm
from app.core.logging import logger
from langchain_core.prompts import ChatPromptTemplate

class ExtractedSubsidiary(BaseModel):
    name: str = Field(description="Name of the subsidiary, joint venture, or division.")
    country: Optional[str] = Field(None, description="Country of incorporation or operations.")
    ownership: Optional[str] = Field("Not Publicly Disclosed", description="Ownership details.")
    relationship_type: str = Field(description="Type: Subsidiary, Brand, Division, Office, Joint Venture.")
    evidence_text: str = Field(description="Paragraph or table row verifying this entry.")

class ExtractionOutput(BaseModel):
    entities: List[ExtractedSubsidiary] = Field(default=[], description="List of corporate entities discovered in the text.")

async def structured_entity_extraction_agent(state: AgentState) -> AgentState:
    """Agent 8: Structured Entity Extraction node mapping chunks/SEC entries to raw claims."""
    document_contents = state.get("document_contents", {})
    document_chunks = state.get("document_chunks", [])
    sec_results = state.get("sec_results", [])
    logs = state.get("logs", [])
    warnings = state.get("warnings", [])
    legal_name = state["company_info"].get("legal_name") or state["query"]
    
    logs.append("Running Structured Entity Extraction Agent...")
    logger.info(f"Structured Entity Extraction Agent parsing document contents for: {legal_name}")
    
    raw_claims = []
    discovered = []
    
    # 1. Map SEC Filing table items to raw claims
    for s_res in sec_results:
        sub_name = s_res.get("name")
        if sub_name:
            claim = {
                "subject": legal_name,
                "predicate": s_res.get("relationship_type", "Subsidiary"),
                "object": sub_name,
                "country": s_res.get("country", "Global"),
                "ownership": s_res.get("ownership", "Wholly-owned"),
                "source_type": s_res.get("source_type", "SEC EDGAR Exhibit 21"),
                "source_url": s_res.get("source_url"),
                "extracted_text": s_res.get("evidence_text", f"Exhibit 21 Disclosure: {sub_name}")
            }
            raw_claims.append(claim)
            discovered.append({
                "name": sub_name,
                "legal_name": sub_name,
                "country": s_res.get("country", "Global"),
                "ownership": s_res.get("ownership", "Wholly-owned"),
                "parent": legal_name,
                "relationship_type": s_res.get("relationship_type", "Subsidiary"),
                "confidence": 0.95,
                "evidences": [{
                    "source_type": s_res.get("source_type", "SEC EDGAR Exhibit 21"),
                    "source_url": s_res.get("source_url"),
                    "extracted_text": claim["extracted_text"]
                }],
                "notes": f"Statutory Exhibit 21 Disclosure for CIK {state['company_info'].get('cik')}"
            })

    if not document_contents and not document_chunks:
        msg = "STRUCTURED_EXTRACTION_SKIPPED_NO_CHUNKS: No document text chunks available for LLM parsing."
        logs.append(msg)
        if not raw_claims:
            warnings.append({"stage": "structured_entity_extraction", "code": "NO_CHUNKS", "message": msg})
        return {
            "raw_claims": raw_claims,
            "extracted_document_results": discovered,
            "logs": logs,
            "warnings": warnings
        }
        
    try:
        llm = get_llm(capability="document_understanding")
        structured_llm = llm.with_structured_output(ExtractionOutput)
        
        system_prompt = (
            "You are a Senior Corporate Intelligence Analyst.\n"
            "Given text/tables, extract any listed subsidiaries, parents, divisions, or brands."
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Company: {company}\nSource URL: {url}\n\nDocument Text:\n{doc_text}")
        ])

        for url, text in document_contents.items():
            doc_text = text[:10000]
            chain = prompt | structured_llm
            result = await chain.ainvoke({
                "company": legal_name,
                "url": url,
                "doc_text": doc_text
            })
            
            suffixes = {"inc", "llc", "ltd", "corp", "co", "plc", "gmbh", "ag", "sa", "bv", "nv", "sarl", "as", "pvt", "private", "limited", "company"}
            for entity in result.entities:
                name_clean = entity.name.strip()
                name_lower = re.sub(r'[^\w\s]', '', name_clean).strip().lower()
                if not name_clean or name_lower in suffixes or len(name_lower) < 3:
                    continue
                    
                claim = {
                    "subject": legal_name,
                    "predicate": entity.relationship_type or "Subsidiary",
                    "object": name_clean,
                    "country": entity.country or "Global",
                    "ownership": entity.ownership or "Not Publicly Disclosed",
                    "source_type": "Annual Report PDF",
                    "source_url": url,
                    "extracted_text": entity.evidence_text
                }
                raw_claims.append(claim)
                
                discovered.append({
                    "name": name_clean,
                    "legal_name": name_clean,
                    "country": entity.country or "Global",
                    "ownership": entity.ownership or "Not Publicly Disclosed",
                    "parent": legal_name,
                    "relationship_type": entity.relationship_type,
                    "confidence": 0.90,
                    "evidences": [{
                        "source_type": "Annual Report PDF",
                        "source_url": url,
                        "extracted_text": entity.evidence_text
                    }],
                    "notes": f"Extracted from document: {url}"
                })
    except Exception as e:
        logger.error(f"Structured entity extraction failed: {str(e)}")
        logs.append(f"Structured extraction error: {str(e)}")

    logs.append(f"Structured Entity Extraction complete. Produced {len(raw_claims)} raw claims and {len(discovered)} extracted entities.")
    return {
        "raw_claims": raw_claims,
        "extracted_document_results": discovered,
        "logs": logs,
        "warnings": warnings
    }
