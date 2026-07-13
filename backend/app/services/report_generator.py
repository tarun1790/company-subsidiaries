import os
import json
import csv
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Canvas subclass to dynamically calculate and print total page count in footers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        # Do not print page numbers on the cover page
        if self._pageNumber == 1:
            return
            
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#4b5563"))
        
        # Header
        self.drawString(inch, 10.5 * inch, "Corporate Subsidiary Intelligence Platform - Official Report")
        self.setStrokeColor(colors.HexColor("#e5e7eb"))
        self.setLineWidth(0.5)
        self.line(inch, 10.4 * inch, 7.5 * inch, 10.4 * inch)
        
        # Footer
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(7.5 * inch, 0.5 * inch, page_text)
        self.drawString(inch, 0.5 * inch, f"Generated on {datetime.now().strftime('%Y-%m-%d')}")
        self.line(inch, 0.65 * inch, 7.5 * inch, 0.65 * inch)
        self.restoreState()


class ReportGenerator:
    @staticmethod
    def generate_pdf(company_name: str, info: Dict[str, Any], subsidiaries: List[Dict[str, Any]], output_path: str):
        """Generates a premium corporate PDF report using ReportLab."""
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54
        )

        styles = getSampleStyleSheet()
        
        # Custom Brand Colors
        c_primary = colors.HexColor("#064e3b")     # Dark Emerald Green
        c_secondary = colors.HexColor("#10b981")   # Emerald Accent
        c_text_dark = colors.HexColor("#1f2937")   # Dark Charcoal
        c_text_muted = colors.HexColor("#4b5563")  # Slate Gray
        c_bg_light = colors.HexColor("#f0fdf4")    # Very Light Green

        # Custom Typography Styles
        title_style = ParagraphStyle(
            'CoverTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=28,
            leading=34,
            textColor=c_primary,
            spaceAfter=15
        )
        
        subtitle_style = ParagraphStyle(
            'CoverSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=14,
            leading=18,
            textColor=c_text_muted,
            spaceAfter=40
        )

        h1_style = ParagraphStyle(
            'Heading1_Custom',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=20,
            leading=24,
            textColor=c_primary,
            spaceBefore=15,
            spaceAfter=10,
            keepWithNext=True
        )

        h2_style = ParagraphStyle(
            'Heading2_Custom',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=14,
            leading=18,
            textColor=c_text_dark,
            spaceBefore=10,
            spaceAfter=8,
            keepWithNext=True
        )

        body_style = ParagraphStyle(
            'Body_Custom',
            parent=styles['BodyText'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=c_text_dark,
            spaceAfter=10
        )

        table_header_style = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=11,
            textColor=colors.white
        )

        table_body_style = ParagraphStyle(
            'TableBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=11,
            textColor=c_text_dark
        )

        story = []

        # =========================================================================
        # PAGE 1: COVER PAGE
        # =========================================================================
        story.append(Spacer(1, 2 * inch))
        story.append(Paragraph(company_name.upper(), title_style))
        story.append(Paragraph("Corporate Subsidiary & Entity Intelligence Report", subtitle_style))
        
        # Divider Line
        story.append(Table(
            [[""]], 
            colWidths=[6.5 * inch], 
            rowHeights=[3], 
            style=TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), c_primary),
                ('TOPPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ])
        ))
        story.append(Spacer(1, 0.5 * inch))

        # Metadata Block
        meta_data = [
            [Paragraph("<b>Resolved Legal Name:</b>", body_style), Paragraph(info.get("legal_name") or company_name, body_style)],
            [Paragraph("<b>CIK Code:</b>", body_style), Paragraph(info.get("cik") or "N/A", body_style)],
            [Paragraph("<b>Ticker Symbol:</b>", body_style), Paragraph(info.get("ticker") or "N/A", body_style)],
            [Paragraph("<b>Primary Domain:</b>", body_style), Paragraph(info.get("domain") or "N/A", body_style)],
            [Paragraph("<b>Headquarters Country:</b>", body_style), Paragraph(info.get("hq_country") or "N/A", body_style)],
            [Paragraph("<b>Generation Date:</b>", body_style), Paragraph(datetime.now().strftime("%B %d, %Y"), body_style)],
        ]
        
        meta_table = Table(meta_data, colWidths=[2.2 * inch, 4.3 * inch])
        meta_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(meta_table)
        story.append(PageBreak())

        # =========================================================================
        # PAGE 2: EXECUTIVE SUMMARY & STATS
        # =========================================================================
        story.append(Paragraph("Executive Summary", h1_style))
        story.append(Paragraph(
            f"This audit report presents a consolidated corporate structure analysis of <b>{info.get('legal_name') or company_name}</b>. "
            f"The underlying research pipeline synthesized records across SEC EDGAR filings, public corporate registries, Wikipedia, "
            f"official website portals, and certificate registries to construct a validated corporate hierarchy.",
            body_style
        ))
        story.append(Spacer(1, 15))

        # Core Statistics Callout Boxes
        num_subs = len(subsidiaries)
        avg_confidence = sum([s.get('confidence', 0.0) for s in subsidiaries]) / max(num_subs, 1)
        countries_list = list(set([s.get('country') for s in subsidiaries if s.get('country')]))
        
        stats_data = [
            [
                Paragraph(f"<font color='{c_primary.hexval()}'><b>Total Entities</b></font><br/><font size='18'><b>{num_subs}</b></font>", body_style),
                Paragraph(f"<font color='{c_primary.hexval()}'><b>Avg Confidence</b></font><br/><font size='18'><b>{avg_confidence * 100:.1f}%</b></font>", body_style),
                Paragraph(f"<font color='{c_primary.hexval()}'><b>Unique Countries</b></font><br/><font size='18'><b>{len(countries_list)}</b></font>", body_style),
            ]
        ]
        stats_table = Table(stats_data, colWidths=[2.1 * inch, 2.1 * inch, 2.1 * inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), c_bg_light),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOX', (0,0), (-1,-1), 1, c_secondary),
            ('INNERGRID', (0,0), (-1,-1), 0.5, c_secondary),
            ('TOPPADDING', (0,0), (-1,-1), 15),
            ('BOTTOMPADDING', (0,0), (-1,-1), 15),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 20))

        # =========================================================================
        # PAGE 3+: VERIFIED SUBSIDIARIES TABLE
        # =========================================================================
        story.append(Paragraph("Verified Subsidiaries & Entities", h1_style))
        story.append(Paragraph(
            "The following list represents entities that have been compiled and resolved from independent data sources. "
            "Each item includes direct references, parent associations, and calculated confidence parameters.",
            body_style
        ))
        story.append(Spacer(1, 10))

        # Table headers
        table_data = [[
            Paragraph("Entity Name", table_header_style),
            Paragraph("Country", table_header_style),
            Paragraph("Ownership", table_header_style),
            Paragraph("Parent Entity", table_header_style),
            Paragraph("Confidence", table_header_style),
        ]]

        for sub in subsidiaries:
            conf_percent = f"{sub.get('confidence', 0.0) * 100:.0f}%"
            table_data.append([
                Paragraph(sub.get("name") or "N/A", table_body_style),
                Paragraph(sub.get("country") or "N/A", table_body_style),
                Paragraph(sub.get("ownership") or "N/A", table_body_style),
                Paragraph(sub.get("parent") or "Direct Parent", table_body_style),
                Paragraph(conf_percent, table_body_style),
            ])

        subs_table = Table(table_data, colWidths=[2.2 * inch, 1.1 * inch, 1.0 * inch, 1.4 * inch, 0.8 * inch], repeatRows=1)
        subs_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), c_primary),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
            ('BOX', (0,0), (-1,-1), 0.5, c_text_muted),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
        ]))
        
        story.append(subs_table)
        story.append(Spacer(1, 20))

        # =========================================================================
        # EVIDENCE MATRIX SECTION
        # =========================================================================
        story.append(Paragraph("Evidence Matrix", h1_style))
        story.append(Paragraph(
            "Traceability is critical. Below is the evidentiary log illustrating the data sources "
            "that verified the corporate registrations and relations.",
            body_style
        ))
        story.append(Spacer(1, 10))

        evidence_headers = [[
            Paragraph("Entity Name", table_header_style),
            Paragraph("Source Type", table_header_style),
            Paragraph("Verified Snippet / Document Source", table_header_style),
        ]]

        has_evidence = False
        for sub in subsidiaries:
            evidences = sub.get("evidences", [])
            for ev in evidences:
                has_evidence = True
                snippet = ev.get("extracted_text") or "Verified via index parsing."
                if len(snippet) > 150:
                    snippet = snippet[:147] + "..."
                
                evidence_headers.append([
                    Paragraph(sub.get("name"), table_body_style),
                    Paragraph(ev.get("source_type"), table_body_style),
                    Paragraph(snippet, table_body_style),
                ])

        if has_evidence:
            ev_table = Table(evidence_headers, colWidths=[1.8 * inch, 1.2 * inch, 3.5 * inch], repeatRows=1)
            ev_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), c_primary),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
                ('BOX', (0,0), (-1,-1), 0.5, c_text_muted),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
            ]))
            story.append(ev_table)
        else:
            story.append(Paragraph("No direct textual evidence logs extracted.", body_style))

        # Build PDF Document
        doc.build(story, canvasmaker=NumberedCanvas)

    @staticmethod
    def generate_excel(company_name: str, subsidiaries: List[Dict[str, Any]], output_path: str):
        """Generates a clean Excel sheet with verified subsidiaries and evidence."""
        # Standard subsidiaries sheet
        rows = []
        for sub in subsidiaries:
            ev_urls = [ev.get("source_url") for ev in sub.get("evidences", []) if ev.get("source_url")]
            rows.append({
                "Entity Name": sub.get("name"),
                "Legal Name": sub.get("legal_name"),
                "HQ Country/Jurisdiction": sub.get("country"),
                "Ownership Share": sub.get("ownership"),
                "Direct Parent": sub.get("parent"),
                "Relationship Type": sub.get("relationship_type"),
                "Registration Number": sub.get("registration_number"),
                "Confidence Score": sub.get("confidence"),
                "Sources Count": len(sub.get("evidences", [])),
                "Source URLs": ", ".join(ev_urls),
                "Notes": sub.get("notes")
            })

        df = pd.DataFrame(rows)
        # Create Excel writer and apply basic styling
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name="Subsidiaries", index=False)
            
            # Autofilter and autofit columns
            workbook = writer.book
            worksheet = writer.sheets["Subsidiaries"]
            worksheet.auto_filter.ref = worksheet.dimensions
            
            for col in worksheet.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = col[0].column_letter
                worksheet.column_dimensions[col_letter].width = max(max_len + 3, 12)

    @staticmethod
    def generate_csv(subsidiaries: List[Dict[str, Any]], output_path: str):
        """Generates a standard CSV report."""
        with open(output_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Name", "Legal Name", "Country", "Ownership", "Parent", 
                "Relationship Type", "Registration Number", "Confidence", "Notes"
            ])
            for sub in subsidiaries:
                writer.writerow([
                    sub.get("name"),
                    sub.get("legal_name"),
                    sub.get("country"),
                    sub.get("ownership"),
                    sub.get("parent"),
                    sub.get("relationship_type"),
                    sub.get("registration_number"),
                    sub.get("confidence"),
                    sub.get("notes")
                ])

    @staticmethod
    def generate_json(company_info: Dict[str, Any], subsidiaries: List[Dict[str, Any]], output_path: str):
        """Generates a structured JSON payload archive."""
        payload = {
            "company_metadata": company_info,
            "subsidiaries": subsidiaries,
            "generated_at": datetime.utcnow().isoformat()
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
