import os
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings
from app.core.logging import logger

from app.core.llm_router import router

def get_llm(capability: str = "general"):
    """Returns the chat model matching the requested capability, utilizing Ollama or Gemini cloud fallbacks."""
    return router.get_llm(capability=capability)
