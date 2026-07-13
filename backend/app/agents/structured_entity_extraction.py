from pydantic import BaseModel, Field
from typing import List, Optional
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
    """Agent 8: Uses structured LLM parsing to extract candidate entities from parsed text blocks."""
    document_contents = state.get("document_contents", {})
    logs = state.get("logs", [])
    legal_name = state["company_info"].get("legal_name") or state["query"]
    
    logs.append("Running Structured Entity Extraction Agent...")
    logger.info(f"Structured Entity Extraction Agent parsing document contents for: {legal_name}")
    
    discovered = []
    
    if not document_contents:
        logs.append("No document text contents available for entity extraction.")
        return state
        
    llm = get_llm()
    structured_llm = llm.with_structured_output(ExtractionOutput)
    
    system_prompt = (
        "You are a Senior Corporate Intelligence Analyst.\n"
        "Given the extracted text/tables from a company's document, "
        "extract any listed subsidiaries, parent organizations, divisions, or brands.\n"
        "Return their name, country, ownership details, relationship type, and the exact evidence row/text fragment."
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Company: {company}\nSource URL: {url}\n\nDocument Text:\n{doc_text}")
    ])

    for url, text in document_contents.items():
        logs.append(f"Extracting entities from document content: {url}")
        try:
            chain = prompt | structured_llm
            result = await chain.ainvoke({
                "company": legal_name,
                "url": url,
                "doc_text": text[:15000] # Safe token limit
            })
            
            for entity in result.entities:
                discovered.append({
                    "name": entity.name,
                    "legal_name": entity.name,
                    "country": entity.country or "Global",
                    "ownership": entity.ownership or "Not Publicly Disclosed",
                    "parent": legal_name,
                    "relationship_type": entity.relationship_type,
                    "confidence": 0.90, # High confidence from official PDF reports
                    "evidences": [{
                        "source_type": "Annual Report PDF",
                        "source_url": url,
                        "extracted_text": entity.evidence_text
                    }],
                    "notes": f"Extracted from official document: {url}"
                })
        except Exception as e:
            logger.error(f"Structured entity extraction failed for {url}: {str(e)}")
            logs.append(f"Structured extraction error for {url}: {str(e)}")

    logs.append(f"Structured Entity Extraction complete. Extracted {len(discovered)} corporate entities.")
    return {
        "extracted_document_results": discovered,
        "logs": logs
    }
