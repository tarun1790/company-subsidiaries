from typing import List, Dict, Any, Optional
from app.services.doc_ast_parser import DocumentASTGraph, DocASTNode
from app.core.logging import logger

class VGraphEngine:
    """Graph-Guided Context Engine for deterministic section traversal (Replacing RAG)."""

    def __init__(self, ast_graph: DocumentASTGraph):
        self.graph = ast_graph

    def traverse_sections_by_keywords(self, keywords: List[str]) -> List[DocASTNode]:
        """Traverses the AST graph to find targeted section nodes matching corporate intelligence keywords."""
        matched_nodes = []
        visited = set()

        def dfs(node: DocASTNode):
            if node.node_id in visited:
                return
            visited.add(node.node_id)

            # Check node title and content against keywords
            title_lower = node.title.lower()
            content_lower = node.content.lower()

            for kw in keywords:
                kw_l = kw.lower()
                if kw_l in title_lower or (node.node_type == "Table" and kw_l in content_lower):
                    matched_nodes.append(node)
                    break

            for child in node.children:
                dfs(child)

        dfs(self.graph.root)
        logger.info(f"[VGraphEngine] Traversed AST Graph for '{self.graph.document_name}'. Found {len(matched_nodes)} matching structural nodes.")
        return matched_nodes

    def extract_subsidiary_tables(self) -> List[str]:
        """Directly targets and extracts tabular subsidiary lists from the AST Graph."""
        table_contents = []
        nodes = self.traverse_sections_by_keywords(["subsidiar", "exhibit 21", "ex-21", "note 18", "holding"])
        
        for node in nodes:
            if node.node_type == "Table":
                table_contents.append(node.content)
            elif node.children:
                for child in node.children:
                    if child.node_type == "Table":
                        table_contents.append(child.content)

        return table_contents

    def get_full_structured_context(self, max_tokens_approx: int = 25000) -> str:
        """Assembles a coherent structural context from AST nodes for long-context LLMs."""
        context_blocks = []
        
        # Priority 1: Tables
        tables = self.extract_subsidiary_tables()
        if tables:
            context_blocks.append("=== EXTRACTED TABULAR STRUCTURES ===")
            context_blocks.extend(tables[:5]) # top 5 tables

        # Priority 2: Key Structural Sections
        key_nodes = self.traverse_sections_by_keywords(["subsidiar", "exhibit 21", "organization", "group structure"])
        if key_nodes:
            context_blocks.append("\n=== STRUCTURAL DOCUMENT SECTIONS ===")
            for n in key_nodes[:10]:
                context_blocks.append(f"--- Section: {n.title} (Page {n.page_number}) ---\n{n.content[:3000]}")

        # Fallback: Top-level section summaries if empty
        if not context_blocks:
            context_blocks.append("=== TOP DOCUMENT SECTIONS ===")
            for child in self.graph.root.children[:15]:
                context_blocks.append(f"--- {child.title or child.node_type} ---\n{child.content[:1500]}")

        full_text = "\n\n".join(context_blocks)
        return full_text[:max_tokens_approx * 4]
