import os
from app.agents.state import AgentState
from app.services.report_generator import ReportGenerator
from app.core.config import settings
from app.core.logging import logger

async def report_agent(state: AgentState) -> AgentState:
    """Agent 9: Generates premium PDF report, Excel sheets, CSV, and JSON representations."""
    company_info = state["company_info"]
    subsidiaries = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    errors = state.get("errors", [])
    
    legal_name = company_info.get("legal_name") or state["query"]
    logs.append("Generating corporate reports (PDF, Excel, CSV, JSON)...")
    logger.info(f"Report Agent starting report compilation for: {legal_name}")

    # Standardize filename format
    safe_name = "".join([c if c.isalnum() else "_" for c in legal_name.lower().strip()]).replace("__", "_")
    
    pdf_filename = f"report_{safe_name}.pdf"
    excel_filename = f"report_{safe_name}.xlsx"
    csv_filename = f"report_{safe_name}.csv"
    json_filename = f"report_{safe_name}.json"
    
    pdf_path = os.path.join(settings.REPORTS_DIR, pdf_filename)
    excel_path = os.path.join(settings.REPORTS_DIR, excel_filename)
    csv_path = os.path.join(settings.REPORTS_DIR, csv_filename)
    json_path = os.path.join(settings.REPORTS_DIR, json_filename)

    try:
        # Generate files asynchronously using to_thread
        import asyncio
        
        logs.append("Compiling premium PDF layout...")
        await asyncio.to_thread(ReportGenerator.generate_pdf, legal_name, company_info, subsidiaries, pdf_path)
        
        logs.append("Building Excel spreadsheets...")
        await asyncio.to_thread(ReportGenerator.generate_excel, legal_name, subsidiaries, excel_path)
        
        logs.append("Writing CSV exports...")
        await asyncio.to_thread(ReportGenerator.generate_csv, subsidiaries, csv_path)
        
        logs.append("Formatting structured JSON payload...")
        await asyncio.to_thread(ReportGenerator.generate_json, company_info, subsidiaries, json_path)
        
        logs.append("Reports generated successfully.")
        
        # Save relative paths so API can serve downloads easily
        return {
            **state,
            "pdf_path": pdf_filename,
            "excel_path": excel_filename,
            "csv_path": csv_filename,
            "json_path": json_filename,
            "logs": logs
        }
        
    except Exception as e:
        error_msg = f"Report generation failed: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)
        logs.append(f"Error compiling reports: {str(e)}")
        return {
            **state,
            "logs": logs,
            "errors": errors
        }
