import os
import httpx
import tempfile
import pdfplumber
from typing import Dict
from app.agents.state import AgentState
from app.core.logging import logger

async def download_and_parse_pdf(url: str, logs: list) -> str:
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                    tmp_file.write(response.content)
                    tmp_path = tmp_file.name
                
                extracted_text = ""
                with pdfplumber.open(tmp_path) as pdf:
                    matched_pages = []
                    for idx, page in enumerate(pdf.pages):
                        text_snippet = (page.extract_text() or "").lower()
                        if any(keyword in text_snippet for keyword in ["subsidiaries", "list of entities", "corporate structure"]):
                            matched_pages.append((idx, page))
                        if len(matched_pages) >= 5:
                            break
                            
                    if not matched_pages:
                        matched_pages = [(idx, page) for idx, page in enumerate(pdf.pages[:3])]

                    for idx, page in matched_pages:
                        page_text = page.extract_text() or ""
                        tables = page.extract_tables()
                        table_text = ""
                        if tables:
                            for table in tables:
                                for row in table:
                                    table_text += " | ".join([str(cell or '') for cell in row]) + "\n"
                        
                        extracted_text += f"\n--- Page {idx+1} ---\n{page_text}\n{table_text}\n"

                os.unlink(tmp_path)
                return extracted_text
            else:
                logs.append(f"HTTP error {response.status_code} downloading PDF: {url}")
    except Exception as e:
        logger.error(f"Error parsing PDF URL {url}: {str(e)}")
        logs.append(f"Error parsing PDF URL: {str(e)}")
    return ""

async def document_intelligence_agent(state: AgentState) -> AgentState:
    """Agent 7: Document Intelligence download and parsing worker."""
    discovered_docs = state.get("discovered_documents", [])
    logs = state.get("logs", [])
    
    logs.append("Running Document Intelligence Agent (parsing and text extraction)...")
    
    document_contents = {}
    
    # We download and parse the top 2 candidate documents to avoid high memory/time usage
    target_docs = discovered_docs[:2]
    for url in target_docs:
        logs.append(f"Downloading and extracting text from: {url}")
        content = await download_and_parse_pdf(url, logs)
        if content.strip():
            document_contents[url] = content
            
    logs.append(f"Text extraction completed for {len(document_contents)} documents.")
    return {
        "document_contents": document_contents,
        "logs": logs
    }
