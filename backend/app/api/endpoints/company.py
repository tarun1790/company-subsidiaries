import uuid
import os
import re
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Dict, Any

from app.core.database import get_db
from app.core.config import settings
from app.core.logging import logger
from app.models.company import Company
from app.models.subsidiary import Subsidiary, Evidence
from app.models.report import Report
from app.schemas.company import CompanyResponse, CompanyCreate
from app.schemas.subsidiary import SubsidiaryResponse
from app.agents.graph import execute_pipeline

router = APIRouter()

@router.get("/history", response_model=List[CompanyResponse])
async def get_search_history(db: AsyncSession = Depends(get_db)):
    """Retrieves list of previously researched companies."""
    try:
        result = await db.execute(
            select(Company).order_by(Company.created_at.desc())
        )
        companies = result.scalars().all()
        return companies
    except Exception as e:
        logger.error(f"Error fetching history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error fetching history.")

@router.get("/{company_id}", response_model=Dict[str, Any])
async def get_company_details(company_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Retrieves full details of a researched company including subsidiaries, evidence, and reports."""
    try:
        # Load company details
        company_result = await db.execute(select(Company).where(Company.id == company_id))
        company = company_result.scalar_one_or_none()
        
        if not company:
            raise HTTPException(status_code=404, detail="Company record not found.")

        # Load subsidiaries with evidences
        subs_result = await db.execute(
            select(Subsidiary)
            .where(Subsidiary.company_id == company_id)
            .options(selectinload(Subsidiary.evidences))
        )
        subsidiaries = subs_result.scalars().all()

        # Load reports paths
        report_result = await db.execute(select(Report).where(Report.company_id == company_id))
        report = report_result.scalar_one_or_none()

        # Format knowledge graph
        kg_nodes = []
        kg_edges = []
        
        parent_id = re.sub(r"[^\w]", "", company.legal_name.lower().strip())
        kg_nodes.append({
            "id": parent_id,
            "label": company.legal_name,
            "type": "Parent",
            "country": company.hq_country or "Global",
            "confidence": 1.0,
            "evidences": []
        })
        
        for sub in subsidiaries:
            sub_id = re.sub(r"[^\w]", "", sub.name.lower().strip())
            kg_nodes.append({
                "id": sub_id,
                "label": sub.name,
                "type": sub.relationship_type,
                "country": sub.country,
                "confidence": sub.confidence,
                "evidences": [{"source_type": ev.source_type, "source_url": ev.source_url, "extracted_text": ev.extracted_text} for ev in sub.evidences]
            })
            
            kg_edges.append({
                "source": parent_id,
                "target": sub_id,
                "relationship": sub.relationship_type,
                "ownership": sub.ownership,
                "confidence": sub.confidence,
                "evidences": [{"source_type": ev.source_type, "source_url": ev.source_url, "extracted_text": ev.extracted_text} for ev in sub.evidences]
            })
            
        knowledge_graph = {
            "nodes": kg_nodes,
            "edges": kg_edges
        }

        company_dict = {
            "id": str(company.id),
            "query_name": company.query_name,
            "legal_name": company.legal_name,
            "cik": company.cik,
            "ticker": company.ticker,
            "domain": company.domain,
            "hq_country": company.hq_country,
            "created_at": company.created_at.isoformat() if company.created_at else None,
            "metadata_fields": company.metadata_fields or {},
            "original_query": (company.metadata_fields or {}).get("original_query"),
            "entity_classification": (company.metadata_fields or {}).get("entity_classification"),
            "confidence": (company.metadata_fields or {}).get("confidence")
        }

        # Format output payload
        return {
            "company": company_dict,
            "subsidiaries": subsidiaries,
            "knowledge_graph": knowledge_graph,
            "reports": {
                "pdf": f"/api/reports/download/{report.pdf_path}" if report and report.pdf_path else None,
                "excel": f"/api/reports/download/{report.excel_path}" if report and report.excel_path else None,
                "csv": f"/api/reports/download/{report.csv_path}" if report and report.csv_path else None,
                "json": f"/api/reports/download/{report.json_path}" if report and report.json_path else None,
            } if report else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching company details: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error fetching details.")


@router.websocket("/ws/pipeline/{query}")
async def pipeline_websocket(websocket: WebSocket, query: str, db: AsyncSession = Depends(get_db)):
    """WebSocket endpoint to initiate, track, and stream the 9-agent pipeline updates."""
    await websocket.accept()
    logger.info(f"WebSocket client connected for query: {query}")

    # Check database cache for recent same query (within 24 hrs) to speed up responses
    try:
        cache_stmt = select(Company).where(Company.query_name.ilike(query.strip())).order_by(Company.created_at.desc())
        cache_res = await db.execute(cache_stmt)
        cached_company = cache_res.scalar_one_or_none()
        
        if cached_company:
            # Check if younger than 24 hours
            from datetime import datetime, timedelta
            # Ensure timezone-naive comparison
            naive_created_at = cached_company.created_at.replace(tzinfo=None)
            if datetime.utcnow() - naive_created_at < timedelta(hours=24):
                # Fetch subsidiaries first to check if cache is empty/failed
                sub_stmt = select(Subsidiary).where(Subsidiary.company_id == cached_company.id).options(selectinload(Subsidiary.evidences))
                sub_res = await db.execute(sub_stmt)
                subs = sub_res.scalars().all()
                
                if len(subs) > 0:
                    await websocket.send_json({
                        "stage": "cached_resolve",
                        "log": "Recent audit results found in cache. Resolving records...",
                        "status": "in_progress"
                    })
                    # Load reports
                    rep_stmt = select(Report).where(Report.company_id == cached_company.id)
                    rep_res = await db.execute(rep_stmt)
                    report = rep_res.scalar_one_or_none()
                    
                    # Serialize and return results
                    serialized_subs = []
                    for s in subs:
                        serialized_subs.append({
                            "name": s.name,
                            "legal_name": s.legal_name,
                            "country": s.country,
                            "ownership": s.ownership,
                            "parent": s.parent,
                            "relationship_type": s.relationship_type,
                            "registration_number": s.registration_number,
                            "confidence": s.confidence,
                            "notes": s.notes,
                            "evidences": [{"source_type": ev.source_type, "source_url": ev.source_url, "extracted_text": ev.extracted_text} for ev in s.evidences]
                        })
                    
                    # Format knowledge graph from cache
                    kg_nodes = []
                    kg_edges = []
                    parent_name = cached_company.legal_name or query
                    parent_id = re.sub(r"[^\w]", "", parent_name.lower().strip())
                    kg_nodes.append({
                        "id": parent_id,
                        "label": parent_name,
                        "type": "Parent",
                        "country": cached_company.hq_country or "Global",
                        "confidence": 1.0,
                        "evidences": []
                    })
                    for s in serialized_subs:
                        sub_id = re.sub(r"[^\w]", "", s["name"].lower().strip())
                        kg_nodes.append({
                            "id": sub_id,
                            "label": s["name"],
                            "type": s["relationship_type"],
                            "country": s["country"],
                            "confidence": s["confidence"],
                            "evidences": s["evidences"]
                        })
                        kg_edges.append({
                            "source": parent_id,
                            "target": sub_id,
                            "relationship": s["relationship_type"],
                            "ownership": s["ownership"],
                            "confidence": s["confidence"],
                            "evidences": s["evidences"]
                        })
                    cached_kg = {
                        "nodes": kg_nodes,
                        "edges": kg_edges
                    }

                    await websocket.send_json({
                        "stage": "done",
                        "log": "Results loaded from local data storage.",
                        "status": "complete",
                        "company_id": str(cached_company.id),
                        "company_info": {
                            "legal_name": cached_company.legal_name,
                            "domain": cached_company.domain,
                            "cik": cached_company.cik,
                            "ticker": cached_company.ticker,
                            "hq_country": cached_company.hq_country,
                            "original_query": (cached_company.metadata_fields or {}).get("original_query"),
                            "entity_classification": (cached_company.metadata_fields or {}).get("entity_classification"),
                            "confidence": (cached_company.metadata_fields or {}).get("confidence"),
                            "metadata_fields": cached_company.metadata_fields
                        },
                        "subsidiaries": serialized_subs,
                        "knowledge_graph": cached_kg,
                        "reports": {
                            "pdf": f"/api/reports/download/{report.pdf_path}" if report and report.pdf_path else None,
                            "excel": f"/api/reports/download/{report.excel_path}" if report and report.excel_path else None,
                            "csv": f"/api/reports/download/{report.csv_path}" if report and report.csv_path else None,
                            "json": f"/api/reports/download/{report.json_path}" if report and report.json_path else None,
                        } if report else None
                    })
                    await websocket.close()
                    return
                else:
                    # Delete empty cached company to run fresh clean audit
                    await db.delete(cached_company)
                    await db.commit()
                    logger.info(f"Deleted empty cached company record for '{query}' to run fresh audit.")
    except Exception as e:
        logger.error(f"Error checking cache: {str(e)}")

    # Hook callback to stream progress logs over WebSocket
    async def progress_hook(stage: str, log_message: str, current_state: Dict[str, Any]):
        try:
            await websocket.send_json({
                "stage": stage,
                "log": log_message,
                "status": "in_progress"
            })
        except Exception as e:
            logger.error(f"WebSocket send error: {str(e)}")
            raise WebSocketDisconnect()

    try:
        # 1. Run multi-agent pipeline
        final_state = await execute_pipeline(query, progress_hook)
        
        comp_info = final_state["company_info"]
        if comp_info.get("status") == "failed":
            await websocket.send_json({
                "stage": "entity_resolution",
                "log": comp_info.get("error") or "Unable to resolve company.",
                "status": "failed"
            })
            await websocket.close()
            return

        # 2. Save results to Database
        
        # Create Company Entry
        meta = comp_info.get("metadata_fields") or {}
        meta["original_query"] = comp_info.get("original_query")
        meta["entity_classification"] = comp_info.get("entity_classification")
        meta["confidence"] = comp_info.get("confidence")

        db_company = Company(
            query_name=query,
            legal_name=comp_info.get("legal_name"),
            cik=comp_info.get("cik"),
            ticker=comp_info.get("ticker"),
            domain=comp_info.get("domain"),
            hq_country=comp_info.get("hq_country"),
            metadata_fields=meta
        )
        db.add(db_company)
        await db.flush() # Populate db_company.id
        
        # Create Subsidiary Entries
        for sub in final_state["subsidiaries"]:
            db_sub = Subsidiary(
                company_id=db_company.id,
                name=sub["name"],
                legal_name=sub.get("legal_name"),
                country=sub.get("country"),
                ownership=sub.get("ownership"),
                parent=sub.get("parent"),
                relationship_type=sub.get("relationship_type"),
                registration_number=sub.get("registration_number"),
                confidence=sub.get("confidence", 0.0),
                notes=sub.get("notes")
            )
            db.add(db_sub)
            await db.flush() # Populate db_sub.id
            
            # Create Evidence Entries
            for ev in sub.get("evidences", []):
                db_ev = Evidence(
                    subsidiary_id=db_sub.id,
                    source_type=ev["source_type"],
                    source_url=ev.get("source_url"),
                    extracted_text=ev.get("extracted_text")
                )
                db.add(db_ev)

        # Create Report Entry
        db_report = Report(
            company_id=db_company.id,
            pdf_path=final_state["pdf_path"],
            excel_path=final_state["excel_path"],
            csv_path=final_state["csv_path"],
            json_path=final_state["json_path"]
        )
        db.add(db_report)
        
        await db.commit()
        logger.info(f"Saved corporate intelligence audit data for '{db_company.legal_name}' (ID: {db_company.id})")

        # 3. Stream final done payload
        await websocket.send_json({
            "stage": "done",
            "log": "Audit compilation saved to data warehouse.",
            "status": "complete",
            "company_id": str(db_company.id),
            "company_info": comp_info,
            "subsidiaries": final_state["subsidiaries"],
            "knowledge_graph": final_state.get("knowledge_graph"),
            "reports": {
                "pdf": f"/api/reports/download/{db_report.pdf_path}" if db_report.pdf_path else None,
                "excel": f"/api/reports/download/{db_report.excel_path}" if db_report.excel_path else None,
                "csv": f"/api/reports/download/{db_report.csv_path}" if db_report.csv_path else None,
                "json": f"/api/reports/download/{db_report.json_path}" if db_report.json_path else None,
            }
        })
        
    except WebSocketDisconnect:
        logger.info("WebSocket connection closed by client.")
    except Exception as e:
        logger.error(f"Error in pipeline websocket execution: {str(e)}")
        try:
            await websocket.send_json({
                "stage": "error",
                "log": f"An unrecoverable error occurred: {str(e)}",
                "status": "failed"
            })
        except Exception:
            pass
    finally:
        await websocket.close()
