import os
import httpx
import tempfile
from typing import Dict, List, Any
from app.agents.state import AgentState
from app.core.logging import logger
from app.core.redis_cache import cache_manager
from app.services.doc_ast_parser import DocASTParser
from app.services.vgraph_engine import VGraphEngine

async def download_and_process_vgraph(url: str, logs: list) -> str:
    cache_key = f"vgraph:{url}"
    try:
        cached = await cache_manager.get(cache_key)
        if cached:
            logs.append(f"Retrieved V-Graph AST context from cache for: {url}")
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
                    logs.append(f"Skipping PDF parse: URL returned non-PDF content.")
                    return ""
                    
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                    tmp_file.write(content_bytes)
                    tmp_path = tmp_file.name
                
                # 1. Build Visual Layout AST Graph
                ast_graph = DocASTParser.parse_pdf_to_ast(tmp_path)
                
                # 2. Run Graph-Guided Traversal Engine
                engine = VGraphEngine(ast_graph)
                vgraph_context = engine.get_full_structured_context(max_tokens_approx=25000)

                os.unlink(tmp_path)
                
                if vgraph_context.strip():
                    try:
                        await cache_manager.set(cache_key, vgraph_context, expire=86400 * 7)
                    except Exception as ce:
                        logger.debug(f"Cache save failed for PDF {url}: {str(ce)}")
                return vgraph_context
            else:
                logs.append(f"HTTP error {response.status_code} downloading PDF: {url}")
    except Exception as e:
        logger.error(f"Error processing PDF URL via V-Graph {url}: {str(e)}")
        logs.append(f"Error processing PDF URL: {str(e)}")
    return ""

async def document_intelligence_agent(state: AgentState) -> AgentState:
    """Agent 7: Advanced V-Graph Document Engine (Vision Layout & AST Graph Traversal, Replacing RAG)."""
    discovered_docs = state.get("discovered_documents", [])
    sec_results = state.get("sec_results", [])
    logs = state.get("logs", [])
    warnings = state.get("warnings", [])
    
    logs.append("Running Advanced V-Graph Document Engine (Vision Layout & AST Graph Traversal)...")
    
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
        logs.append(f"Ingesting PDF via V-Graph Engine: {url}")
        content = await download_and_process_vgraph(url, logs)
        if content.strip():
            document_contents[url] = content
            # Pass structural section nodes to downstream long-context LLMs
            document_chunks.append({
                "doc_url": url,
                "chunk_id": f"{url}#vgraph_ast",
                "text": content
            })

    logs.append(f"V-Graph AST Traversal completed. Generated {len(document_chunks)} structural AST nodes across {len(document_contents)} active files.")
    return {
        "source_documents": source_documents,
        "document_chunks": document_chunks,
        "document_contents": document_contents,
        "logs": logs,
        "warnings": warnings
    }
