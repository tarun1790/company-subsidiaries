import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.logging import logger

router = APIRouter()

@router.get("/download/{filename}")
async def download_report_file(filename: str):
    """Serves generated report documents (PDF, XLSX, CSV, JSON)."""
    # Prevent directory traversal attacks
    clean_filename = os.path.basename(filename)
    file_path = os.path.join(settings.REPORTS_DIR, clean_filename)
    
    if not os.path.exists(file_path):
        logger.error(f"Report download request failed: File not found at '{file_path}'")
        raise HTTPException(status_code=404, detail="Requested report file does not exist.")
        
    # Map file extensions to content types
    media_types = {
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".csv": "text/csv",
        ".json": "application/json"
    }
    
    _, ext = os.path.splitext(clean_filename.lower())
    content_type = media_types.get(ext, "application/octet-stream")
    
    return FileResponse(
        path=file_path,
        media_type=content_type,
        filename=clean_filename
    )
