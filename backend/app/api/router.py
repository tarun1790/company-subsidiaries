from fastapi import APIRouter
from app.api.endpoints.company import router as company_router
from app.api.endpoints.report import router as report_router
from app.api.endpoints.feedback import router as feedback_router

api_router = APIRouter()

# Include endpoints
api_router.include_router(company_router, prefix="/companies", tags=["Companies"])
api_router.include_router(report_router, prefix="/reports", tags=["Reports"])
api_router.include_router(feedback_router, prefix="/feedback", tags=["Active Learning Feedback"])
