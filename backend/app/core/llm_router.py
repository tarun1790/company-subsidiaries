import os
import yaml
import httpx
import time
from typing import Dict, Any, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.globals import set_llm_cache
from langchain_core.caches import InMemoryCache
from langchain_core.callbacks import BaseCallbackHandler
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings
from app.core.logging import logger

# Initialize LangChain global LLM response cache
set_llm_cache(InMemoryCache())

_config_cache = None

def load_llm_config() -> Dict[str, Any]:
    global _config_cache
    if _config_cache is not None:
        return _config_cache
        
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_config.yaml")
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                _config_cache = yaml.safe_load(f)
                return _config_cache
    except Exception as e:
        logger.error(f"Failed to load llm_config.yaml: {str(e)}")
        
    # Hardcoded default fallback configuration
    _config_cache = {
        "inference": {
            "backend": "ollama",
            "base_url": "http://localhost:11434",
            "allow_cloud_fallback": False
        },
        "capabilities": {
            "entity_resolution": {"primary": "qwen2.5:14b", "fallback_chain": ["qwen2.5:7b", "deepseek-r1:8b", "qwen2.5"], "cloud_fallback": "gemini-2.5-pro"},
            "document_understanding": {"primary": "qwen2.5:14b", "fallback_chain": ["deepseek-r1:8b", "qwen2.5"], "cloud_fallback": "gemini-2.5-pro"},
            "reasoning": {"primary": "deepseek-r1:8b", "fallback_chain": ["qwen2.5:7b", "qwen2.5"], "cloud_fallback": "gemini-2.5-pro"},
            "classification": {"primary": "gemma2:9b", "fallback_chain": ["qwen2.5:7b", "qwen2.5"], "cloud_fallback": "gemini-2.5-flash"},
            "json_generation": {"primary": "qwen2.5:14b", "fallback_chain": ["gemma2:9b", "qwen2.5"], "cloud_fallback": "gemini-2.5-flash"},
            "code_generation": {"primary": "qwen2.5:14b", "fallback_chain": ["qwen2.5"], "cloud_fallback": "gemini-2.5-flash"},
            "verification": {"primary": "deepseek-r1:8b", "fallback_chain": ["qwen2.5:7b", "qwen2.5"], "cloud_fallback": "gemini-2.5-pro"},
            "general": {"primary": "qwen2.5:14b", "fallback_chain": ["gemma2:9b", "qwen2.5"], "cloud_fallback": "gemini-2.5-flash"}
        }
    }
    return _config_cache

class ModelHealthMonitor:
    """Monitors model availability, latency, memory pressure, and consecutive failures."""
    def __init__(self):
        self.consecutive_failures: Dict[str, int] = {}
        self.average_latency: Dict[str, float] = {}
        self.request_counts: Dict[str, int] = {}
        self.active_queues: Dict[str, int] = {}

    def report_success(self, model_name: str, duration: float):
        self.consecutive_failures[model_name] = 0
        self.request_counts[model_name] = self.request_counts.get(model_name, 0) + 1
        prev_lat = self.average_latency.get(model_name, 0.0)
        if prev_lat == 0.0:
            self.average_latency[model_name] = duration
        else:
            self.average_latency[model_name] = (prev_lat * 0.8) + (duration * 0.2)

    def report_failure(self, model_name: str):
        self.consecutive_failures[model_name] = self.consecutive_failures.get(model_name, 0) + 1

    def is_healthy(self, model_name: str) -> bool:
        return self.consecutive_failures.get(model_name, 0) < 3

    def get_status_report(self) -> Dict[str, Any]:
        return {
            "consecutive_failures": self.consecutive_failures,
            "average_latency": self.average_latency,
            "request_counts": self.request_counts,
            "active_queues": self.active_queues
        }

class LoadBalancerCallbackHandler(BaseCallbackHandler):
    """Automatically logs and tracks queue length and latency telemetry in real-time."""
    def __init__(self, model_name: str, health_monitor: ModelHealthMonitor):
        self.model_name = model_name
        self.health_monitor = health_monitor
        self.start_time = 0.0

    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
        self.health_monitor.active_queues[self.model_name] = self.health_monitor.active_queues.get(self.model_name, 0) + 1
        self.start_time = time.time()
        logger.debug(f"[TELEMETRY] Start run on '{self.model_name}' (Queue: {self.health_monitor.active_queues[self.model_name]})")

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        self.health_monitor.active_queues[self.model_name] = max(0, self.health_monitor.active_queues.get(self.model_name, 1) - 1)
        duration = time.time() - self.start_time
        self.health_monitor.report_success(self.model_name, duration)
        logger.debug(f"[TELEMETRY] Finished run on '{self.model_name}' in {duration:.2f}s (Queue: {self.health_monitor.active_queues[self.model_name]})")

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self.health_monitor.active_queues[self.model_name] = max(0, self.health_monitor.active_queues.get(self.model_name, 1) - 1)
        self.health_monitor.report_failure(self.model_name)
        logger.warning(f"[TELEMETRY] Error on '{self.model_name}': {str(error)}")

class LLMRouter:
    def __init__(self):
        self.config = load_llm_config()
        inf_config = self.config.get("inference", {})
        self.backend = inf_config.get("backend", "ollama")
        self.base_url = inf_config.get("base_url", "http://localhost:11434")
        self.allow_cloud_fallback = inf_config.get("allow_cloud_fallback", False)
        
        self.google_api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        self.health_monitor = ModelHealthMonitor()

    def check_local_server_online(self) -> bool:
        """Pings local inference server to verify availability."""
        try:
            ping_url = self.base_url
            if self.backend == "ollama":
                ping_url = f"{self.base_url}/api/tags"
            resp = httpx.get(ping_url, timeout=0.5)
            return resp.status_code == 200
        except Exception:
            return False

    def build_chat_model(self, model_name: str) -> BaseChatModel:
        """Instantiates ChatModel wrapper and registers telemetry load balancing callback handler."""
        cb_handler = LoadBalancerCallbackHandler(model_name, self.health_monitor)
        
        if self.backend == "ollama":
            return ChatOllama(
                base_url=self.base_url,
                model=model_name,
                temperature=0.0,
                callbacks=[cb_handler]
            )
        elif self.backend in ["vllm", "openai_compatible", "llama.cpp"]:
            return ChatOpenAI(
                base_url=self.base_url,
                api_key="none",
                model=model_name,
                temperature=0.0,
                callbacks=[cb_handler]
            )
        else:
            raise ValueError(f"Unsupported inference backend configuration: {self.backend}")

    def get_llm(self, capability: str = "general") -> BaseChatModel:
        """Dynamically routes requests to best healthy model using queue load balancing and fallback chains."""
        caps = self.config.get("capabilities", {})
        cap_config = caps.get(capability) or caps.get("general")
        
        primary_model = cap_config.get("primary", "qwen2.5:14b")
        local_fallbacks = cap_config.get("fallback_chain", ["qwen2.5"])
        cloud_fallback = cap_config.get("cloud_fallback", "gemini-2.5-flash")
        
        local_server_online = self.check_local_server_online()
        candidates = [primary_model] + local_fallbacks
        
        # 1. Filter healthy candidates
        healthy_candidates = [c for c in candidates if self.health_monitor.is_healthy(c)]
        if not healthy_candidates:
            healthy_candidates = candidates
            
        # 2. Load Balancer: Sort candidates by active queue length to distribute query load
        healthy_candidates.sort(key=lambda m: self.health_monitor.active_queues.get(m, 0))
        
        if local_server_online:
            logger.info(f"Local {self.backend} server online. Load balanced fallback chain: {healthy_candidates}")
            models_chain = []
            for model in healthy_candidates:
                models_chain.append(self.build_chat_model(model))
                
            if self.allow_cloud_fallback and self.google_api_key:
                cloud_model = ChatGoogleGenerativeAI(
                    model=cloud_fallback,
                    google_api_key=self.google_api_key,
                    temperature=0.0,
                    max_retries=2
                )
                models_chain.append(cloud_model)
                
            if len(models_chain) == 1:
                return models_chain[0]
            return models_chain[0].with_fallbacks(models_chain[1:])
            
        else:
            if self.allow_cloud_fallback and self.google_api_key:
                logger.warning(f"Local server unreachable at {self.base_url}. Falling back directly to cloud model '{cloud_fallback}'...")
                return ChatGoogleGenerativeAI(
                    model=cloud_fallback,
                    google_api_key=self.google_api_key,
                    temperature=0.0,
                    max_retries=2
                )
            else:
                error_msg = (
                    f"Local inference server ({self.backend}) is offline or unreachable at {self.base_url}. "
                    "Since cloud fallbacks are disabled in Enterprise v4.1 (to maintain 100% self-hosted open-source privacy), "
                    "this request cannot be processed. Please start your local Ollama/vLLM inference server."
                )
                logger.critical(error_msg)
                raise ConnectionError(error_msg)

# Singleton router instance
router = LLMRouter()
