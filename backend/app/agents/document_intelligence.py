import os
import httpx
import tempfile
import pdfplumber
import pypdf
from typing import Dict
from app.agents.state import AgentState
from app.core.logging import logger
from app.core.redis_cache import cache_manager

async def download_and_parse_pdf(url: str, logs: list) -> str:
    cache_key = f"pdf:{url}"
    try:
        cached = await cache_manager.get(cache_key)
        if cached:
            logs.append(f"Retrieved parsed document text from cache for: {url}")
            return cached
    except Exception as ce:
        logger.debug(f"Cache lookup failed for PDF {url}: {str(ce)}")

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                content_bytes = response.content
                if not content_bytes.startswith(b"%PDF"):
                    logs.append(f"Skipping PDF parse: URL returned non-PDF content (signature mismatch).")
                    return ""
                    
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                    tmp_file.write(content_bytes)
                    tmp_path = tmp_file.name
                
                extracted_text = ""
                matched_page_indices = []
                
                # Step 1: Use fast pypdf to scan page texts for keywords
                try:
                    reader = pypdf.PdfReader(tmp_path)
                    for idx, page in enumerate(reader.pages):
                        try:
                            text_snippet = (page.extract_text() or "").lower()
                            if any(keyword in text_snippet for keyword in ["subsidiaries", "list of entities", "corporate structure"]):
                                matched_page_indices.append(idx)
                            if len(matched_page_indices) >= 5:
                                break
                        except Exception:
                            pass
                    
                    if not matched_page_indices:
                        matched_page_indices = list(range(min(3, len(reader.pages))))
                except Exception as pe:
                    logger.warning(f"Fast PDF scan failed: {str(pe)}")
                    matched_page_indices = [0, 1, 2]
                
                # Step 2: Use pdfplumber only for the matched pages to extract formatted text/tables
                if matched_page_indices:
                    with pdfplumber.open(tmp_path) as pdf:
                        for idx in matched_page_indices:
                            if idx < len(pdf.pages):
                                page = pdf.pages[idx]
                                page_text = page.extract_text() or ""
                                tables = page.extract_tables()
                                table_text = ""
                                if tables:
                                    for table in tables:
                                        for row in table:
                                            table_text += " | ".join([str(cell or '') for cell in row]) + "\n"
                                
                                extracted_text += f"\n--- Page {idx+1} ---\n{page_text}\n{table_text}\n"

                os.unlink(tmp_path)
                if extracted_text.strip():
                    try:
                        await cache_manager.set(cache_key, extracted_text, expire=86400 * 7) # Cache for 7 days
                    except Exception as ce:
                        logger.debug(f"Cache save failed for PDF {url}: {str(ce)}")
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
            try:
                from app.services.vector_retrieval import retrieval_service
                await retrieval_service.index_document(url, content)
                logs.append(f"Document indexed successfully in Qdrant Vector database: {url}")
            except Exception as ve:
                logger.error(f"Vector indexing failed for {url}: {str(ve)}")
                logs.append(f"Vector indexing warning: {str(ve)}")
            
    logs.append(f"Text extraction completed for {len(document_contents)} documents.")
    return {
        "document_contents": document_contents,
        "logs": logs
    }
