import os
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings
from app.core.logging import logger

def get_llm():
    """Initializes and returns the ChatGoogleGenerativeAI model with automatic failover to Flash."""
    api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY is not configured. LLM calls may fail.")
        
    pro_model = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        google_api_key=api_key,
        temperature=0.0,
        max_retries=3
    )
    
    flash_model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0.0,
        max_retries=5
    )
    
    return pro_model.with_fallbacks([flash_model])
