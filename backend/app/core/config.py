import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Corporate Subsidiary Intelligence Platform"
    API_V1_STR: str = "/api"
    
    # Environment configs
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgrespassword@localhost:5432/subsidiary_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # AI models & Search APIs
    GEMINI_API_KEY: Optional[str] = None
    TAVILY_API_KEY: Optional[str] = None
    
    # File Paths
    REPORTS_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports")
    
    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()

# Ensure reports directory exists
os.makedirs(settings.REPORTS_DIR, exist_ok=True)
