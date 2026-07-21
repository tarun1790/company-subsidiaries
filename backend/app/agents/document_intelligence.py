import os
import httpx
import tempfile
import pdfplumber
import pypdf
from typing import Dict, List, Any
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
                        await cache_manager.set(cache_key, extracted_text, expire=86400 * 7)
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
    """Agent 7: Document Intelligence ingestion worker with explicit skip reasons and canonical key output."""
    discovered_docs = state.get("discovered_documents", [])
    sec_results = state.get("sec_results", [])
    logs = state.get("logs", [])
    warnings = state.get("warnings", [])
    
    logs.append("Running Document Intelligence Agent (parsing and text extraction)...")
    
    source_documents = []
    document_chunks = []
    document_contents = {}
    
    # 1. Gather all document sources (discovered PDFs + SEC filings)
    for doc in discovered_docs:
        source_documents.append({"url": doc, "type": "pdf"})
        
    for sec_res in sec_results:
        if sec_res.get("source_url"):
            source_documents.append({"url": sec_res["source_url"], "type": "sec_filing"})
            
    if not source_documents:
        msg = "DOCUMENT_INTELLIGENCE_SKIPPED_NO_SOURCE_DOCUMENTS: No discovered PDF documents or SEC filings available to ingest."
        logs.append(msg)
        warnings.append({"stage": "document_intelligence", "code": "NO_SOURCE_DOCUMENTS", "message": msg})
        return {
            "source_documents": [],
            "document_chunks": [],
            "document_contents": {},
            "logs": logs,
            "warnings": warnings
        }

    target_docs = [d["url"] for d in source_documents[:3]]
    for url in target_docs:
        logs.append(f"Downloading and extracting text from: {url}")
        content = await download_and_parse_pdf(url, logs)
        if content.strip():
            document_contents[url] = content
            # Create document chunks for downstream structured entity extraction
            chunks = [content[i:i+2000] for i in range(0, len(content), 1800)]
            for c_idx, chunk in enumerate(chunks):
                document_chunks.append({
                    "doc_url": url,
                    "chunk_id": f"{url}#chunk_{c_idx}",
                    "text": chunk
                })

    logs.append(f"Text extraction completed. Created {len(document_chunks)} document chunks across {len(document_contents)} active files.")
    return {
        "source_documents": source_documents,
        "document_chunks": document_chunks,
        "document_contents": document_contents,
        "logs": logs,
        "warnings": warnings
    }
