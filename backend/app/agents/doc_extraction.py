import os
import re
import httpx
import tempfile
import pdfplumber
from pydantic import BaseModel, Field
from typing import List, Optional
from app.agents.state import AgentState
from app.agents.llm import get_llm
from app.core.logging import logger
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import DuckDuckGoSearchRun

class DocSubsidiary(BaseModel):
    name: str = Field(description="Name of the subsidiary, joint venture, or division.")
    country: Optional[str] = Field(None, description="Country of incorporation or operations.")
    ownership: Optional[str] = Field("100%", description="Ownership details.")
    relationship_type: str = Field(description="Type: Subsidiary, Brand, Division, Office, Joint Venture.")
    evidence_text: str = Field(description="Paragraph or table row verifying this entry.")

class DocExtractionOutput(BaseModel):
    entities: List[DocSubsidiary] = Field(default=[], description="List of corporate entities discovered in the document.")

async def doc_extraction_agent(state: AgentState) -> AgentState:
    """Agent 6: Searches for official PDF documents (Annual Reports, Sustainability Reports), parses tables/text, and extracts entities."""
    company_info = state["company_info"]
    subsidiaries = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    errors = state.get("errors", [])
    
    legal_name = company_info.get("legal_name") or state["query"]
    logs.append("Running Document Extraction Agent...")
    logger.info(f"Document Extraction Agent searching for PDF docs for: {legal_name}")

    discovered = []
    pdf_url = None
    
    # 1. Search for a PDF document
    try:
        ddg = DuckDuckGoSearchRun()
        search_query = f"{legal_name} annual report filetype:pdf"
        logs.append(f"Searching web for official reports (annual report, corporate structures)...")
        search_res = ddg.run(search_query)
        
        # Simple extraction of first PDF url from search description
        urls = re.findall(r'https?://[^\s<>"]+\.pdf', search_res)
        if urls:
            pdf_url = urls[0]
            logs.append(f"Found candidate PDF report: {pdf_url}")
    except Exception as e:
        logger.warning(f"Error searching for PDF reports: {str(e)}")

    if pdf_url:
        try:
            logs.append(f"Downloading PDF report: {pdf_url}...")
            # Download file to a temporary location
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                response = await client.get(pdf_url, headers=headers)
                
                if response.status_code == 200:
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                        tmp_file.write(response.content)
                        tmp_path = tmp_file.name
                    
                    logs.append("Parsing PDF pages (looking for subsidiaries list or tables)...")
                    extracted_text = ""
                    
                    with pdfplumber.open(tmp_path) as pdf:
                        # Rather than reading the entire PDF (which could be hundreds of pages),
                        # we search page indices or read pages matching keywords like "subsidiary", "entities", "structure"
                        matched_pages = []
                        for idx, page in enumerate(pdf.pages):
                            # Check first 5 pages (index, highlights) and any page with "subsidiary" or "holding"
                            text_snippet = (page.extract_text() or "").lower()
                            if "subsidiaries" in text_snippet or "list of entities" in text_snippet or "corporate structure" in text_snippet:
                                matched_pages.append((idx, page))
                            # Limit page matching to prevent too many scans
                            if len(matched_pages) >= 5:
                                break
                                
                        # Fallback: if no pages matched, read first 3 pages
                        if not matched_pages:
                            matched_pages = [(idx, page) for idx, page in enumerate(pdf.pages[:3])]

                        for idx, page in matched_pages:
                            logs.append(f"Extracting table data and text from PDF page {idx + 1}...")
                            page_text = page.extract_text() or ""
                            # Append table text if tables exist on page
                            tables = page.extract_tables()
                            table_text = ""
                            if tables:
                                for table in tables:
                                    for row in table:
                                        table_text += " | ".join([str(cell or '') for cell in row]) + "\n"
                            
                            extracted_text += f"\n--- Page {idx+1} ---\n{page_text}\n{table_text}\n"

                    # Remove temp file
                    os.unlink(tmp_path)

                    # Send to LLM for extraction
                    if len(extracted_text.strip()) > 100:
                        llm = get_llm()
                        structured_llm = llm.with_structured_output(DocExtractionOutput)
                        
                        system_prompt = (
                            "You are a Senior Corporate Intelligence Analyst.\n"
                            "Given the extracted text/tables from a company's PDF Annual Report, "
                            "extract any listed subsidiaries, parent organizations, divisions, or brands.\n"
                            "Return their name, country, ownership percentage, relationship type, and the exact row/text fragment."
                        )
                        
                        prompt = ChatPromptTemplate.from_messages([
                            ("system", system_prompt),
                            ("user", "Company: {company}\nPDF URL: {pdf_url}\n\nDocument Snippet:\n{doc_text}")
                        ])
                        
                        chain = prompt | structured_llm
                        result = await chain.ainvoke({
                            "company": legal_name,
                            "pdf_url": pdf_url,
                            "doc_text": extracted_text[:15000] # Limit context size
                        })
                        
                        for entity in result.entities:
                            discovered.append({
                                "name": entity.name,
                                "legal_name": entity.name,
                                "country": entity.country,
                                "ownership": entity.ownership,
                                "parent": legal_name,
                                "relationship_type": entity.relationship_type,
                                "confidence": 0.90, # High confidence from official PDF reports
                                "evidences": [{
                                    "source_type": "Annual Report PDF",
                                    "source_url": pdf_url,
                                    "extracted_text": entity.evidence_text
                                }],
                                "notes": f"Extracted from official PDF document: {pdf_url}"
                            })
                            
                        logs.append(f"Extracted {len(discovered)} subsidiaries from downloaded PDF document.")
                else:
                    logs.append(f"Failed to download PDF (HTTP {response.status_code}).")
        except Exception as e:
            error_msg = f"PDF download or parsing error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            logs.append(f"Error parsing PDF document: {str(e)}")
    else:
        logs.append("No official PDF report URLs discovered. Skipping document-level extraction.")

    return {
        **state,
        "subsidiaries": subsidiaries + discovered,
        "logs": logs
    }
