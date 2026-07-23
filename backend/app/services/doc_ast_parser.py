import os
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.core.logging import logger

class DocASTNode(BaseModel):
    node_id: str
    node_type: str = Field(description="Section, Heading, Table, Paragraph, Container")
    title: str = ""
    content: str = ""
    page_number: int = 1
    bounding_box: Optional[List[float]] = None  # [x0, top, x1, bottom]
    children: List['DocASTNode'] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DocumentASTGraph(BaseModel):
    document_name: str
    total_pages: int = 1
    root: DocASTNode
    sections_map: Dict[str, List[str]] = Field(default_factory=dict) # Section Title -> Node IDs

class DocASTParser:
    """Parses PDF layout geometry and structural sections into a Document AST Graph."""

    @classmethod
    def parse_pdf_to_ast(cls, pdf_path: str) -> DocumentASTGraph:
        """Parses a local PDF document into a visual layout AST graph."""
        doc_name = os.path.basename(pdf_path)
        logger.info(f"[DocASTParser] Parsing document geometry & AST graph for: {doc_name}")
        
        root = DocASTNode(
            node_id="root_0",
            node_type="Document",
            title=doc_name,
            content=f"Document Root for {doc_name}"
        )
        
        sections_map = {}
        total_pages = 1
        
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                current_section_node = root
                
                for idx, page in enumerate(pdf.pages):
                    page_num = idx + 1
                    page_text = page.extract_text() or ""
                    
                    # 1. Extract Tables visually intact
                    tables = page.extract_tables()
                    for t_idx, table_data in enumerate(tables):
                        if not table_data:
                            continue
                        
                        # Reconstruct tabular markdown representation
                        table_str_rows = []
                        for row in table_data:
                            clean_row = [str(c).replace('\n', ' ').strip() if c else "" for c in row]
                            table_str_rows.append(" | ".join(clean_row))
                        table_content = "\n".join(table_str_rows)
                        
                        tbl_node = DocASTNode(
                            node_id=f"tbl_{page_num}_{t_idx}",
                            node_type="Table",
                            title=f"Page {page_num} Table {t_idx+1}",
                            content=table_content,
                            page_number=page_num,
                            metadata={"rows": len(table_data), "cols": len(table_data[0]) if table_data else 0}
                        )
                        current_section_node.children.append(tbl_node)
                    
                    # 2. Extract Headings & Paragraphs
                    lines = page_text.split('\n')
                    for l_idx, line in enumerate(lines):
                        line_s = line.strip()
                        if not line_s:
                            continue
                            
                        # Detect section headers (e.g. ITEM 15, EXHIBIT 21, NOTE 18, SUBSIDIARIES)
                        if re.match(r'^(ITEM\s+\d+|EXHIBIT\s+\d+|NOTE\s+\d+|SUBSIDIARIES|CONSOLIDATED|SCHEDULE|PART\s+[I|V|X]+)', line_s, re.IGNORECASE) or (len(line_s) < 80 and line_s.isupper()):
                            sec_node = DocASTNode(
                                node_id=f"sec_{page_num}_{l_idx}",
                                node_type="Section",
                                title=line_s,
                                content=line_s,
                                page_number=page_num
                            )
                            root.children.append(sec_node)
                            current_section_node = sec_node
                            
                            sec_title_lower = line_s.lower()
                            if sec_title_lower not in sections_map:
                                sections_map[sec_title_lower] = []
                            sections_map[sec_title_lower].append(sec_node.node_id)
                        else:
                            para_node = DocASTNode(
                                node_id=f"p_{page_num}_{l_idx}",
                                node_type="Paragraph",
                                title="",
                                content=line_s,
                                page_number=page_num
                            )
                            current_section_node.children.append(para_node)
                            
        except Exception as e:
            logger.warning(f"[DocASTParser] Fallback parsing due to pdfplumber warning/error: {e}")
            # Fallback layout extraction using basic text split
            try:
                import pypdf
                reader = pypdf.PdfReader(pdf_path)
                total_pages = len(reader.pages)
                for idx, page in enumerate(reader.pages):
                    page_text = page.extract_text() or ""
                    p_node = DocASTNode(
                        node_id=f"pypdf_{idx+1}",
                        node_type="Paragraph",
                        title=f"Page {idx+1} Text",
                        content=page_text,
                        page_number=idx+1
                    )
                    root.children.append(p_node)
            except Exception as pe:
                logger.error(f"[DocASTParser] All PDF parsers failed for {pdf_path}: {pe}")
                
        return DocumentASTGraph(
            document_name=doc_name,
            total_pages=total_pages,
            root=root,
            sections_map=sections_map
        )
