import os
import time
from typing import Dict, Any, List
from app.agents.state import AgentState, emit_node_telemetry
from app.services.report_generator import ReportGenerator
from app.core.config import settings
from app.core.logging import logger

async def report_agent(state: AgentState) -> AgentState:
    """Agent: Generates V3 Audit PDF report, Excel sheets, CSV, and JSON representations."""
    start_time = time.time()
    company_info = state.get("company_info", {})
    subsidiaries = state.get("subsidiaries", [])
    logs = state.get("logs", [])
    errors = state.get("errors", [])
    
    legal_name = company_info.get("legal_name") or state.get("query", "Unknown")
    logs.append("Generating corporate reports (PDF, Excel, CSV, JSON)...")
    logger.info(f"Report Agent starting report compilation for: {legal_name}")

    safe_name = "".join([c if c.isalnum() else "_" for c in legal_name.lower().strip()]).replace("__", "_")
    pdf_filename = f"report_{safe_name}.pdf"
    excel_filename = f"report_{safe_name}.xlsx"
    csv_filename = f"report_{safe_name}.csv"
    json_filename = f"report_{safe_name}.json"
    
    pdf_path = os.path.join(settings.REPORTS_DIR, pdf_filename)
    excel_path = os.path.join(settings.REPORTS_DIR, excel_filename)
    csv_path = os.path.join(settings.REPORTS_DIR, csv_filename)
    json_path = os.path.join(settings.REPORTS_DIR, json_filename)

    # Group entities by status
    entities_by_status = {
        "Confirmed": [], "Probable": [], "Unverified": [], "Conflicting": [],
        "Historical": [], "Former": [], "Inactive": [], "Dissolved": [], "Excluded": [], "Unknown": []
    }
    
    # We use candidate_entities because it retains Excluded ones
    candidates = state.get("candidate_entities", [])
    for cand in candidates:
        status = cand.get("status", "Unknown")
        if status in entities_by_status:
            entities_by_status[status].append(cand)
            
    # Include any fused subsidiaries that were upgraded
    for sub in subsidiaries:
        status = sub.get("status", "Unknown")
        if status in entities_by_status:
            # Check for duplicates by name
            if not any(e.get("name") == sub.get("name") for e in entities_by_status[status]):
                entities_by_status[status].append(sub)

    v3_report_data = {
        "report_metadata": {
            "run_id": f"run_{int(time.time())}",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "target_company": legal_name,
            "mode": state.get("execution_summary", {}).get("mode", "enterprise_audit")
        },
        "executive_summary": {
            "confirmed_count": len(entities_by_status["Confirmed"]),
            "probable_count": len(entities_by_status["Probable"]),
            "unverified_count": len(entities_by_status["Unverified"]),
            "conflicting_count": len(entities_by_status["Conflicting"]),
            "excluded_count": len(entities_by_status["Excluded"]),
            "completeness_score": state.get("coverage_score", {}).get("overall", 0.0)
        },
        "entities_by_status": entities_by_status,
        "graph_validation": state.get("knowledge_graph", {}).get("graph_validation", {}),
        "evidence_ledger": state.get("evidence_records", []),
        "company_info": company_info
    }

    try:
        import asyncio
        await asyncio.to_thread(ReportGenerator.generate_pdf, legal_name, company_info, subsidiaries, pdf_path)
        await asyncio.to_thread(ReportGenerator.generate_excel, legal_name, subsidiaries, excel_path)
        await asyncio.to_thread(ReportGenerator.generate_csv, subsidiaries, csv_path)
        await asyncio.to_thread(ReportGenerator.generate_json_v3, v3_report_data, json_path)
        
        logs.append("Reports generated successfully.")
        emit_node_telemetry("report_agent", state, start_time, "success")
        
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
        emit_node_telemetry("report_agent", state, start_time, "error")
        return {
            **state,
            "logs": logs,
            "errors": errors
        }
