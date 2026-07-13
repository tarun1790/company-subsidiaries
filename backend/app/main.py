import asyncio
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.core.redis_cache import cache_manager
from app.core.logging import logger
from app.api.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Asynchronous corporate subsidiary discovery & validation platform.",
    version="1.0.0"
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Corporate Subsidiary Intelligence Platform backend...")
    
    # 1. Connect to Redis cache
    await cache_manager.connect()
    
    # 2. Initialize database schemas (create tables if not exist)
    # We yield a few retries to let PostgreSQL container finish spawning in docker-compose
    retries = 5
    while retries > 0:
        try:
            await init_db()
            break
        except Exception as e:
            retries -= 1
            logger.warning(f"Database connection waiting... Retries left: {retries}. Error: {str(e)}")
            await asyncio.sleep(3)
            if retries == 0:
                logger.critical("Could not connect to database on startup. Exiting.")

@app.get("/")
async def root():
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "api_docs": "/docs"
    }

# Include routers
app.include_router(api_router, prefix=settings.API_V1_STR)
