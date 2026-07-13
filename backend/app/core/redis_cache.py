import json
import redis.asyncio as redis
from typing import Optional, Any
from app.core.config import settings
from app.core.logging import logger

class RedisCacheManager:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self._fallback_db = {} # In-memory fallback if Redis is down

    async def connect(self):
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            await self.redis_client.ping()
            logger.info("Connected to Redis cache successfully.")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis cache: {str(e)}. Falling back to in-memory cache.")
            self.redis_client = None

    async def get(self, key: str) -> Optional[str]:
        if self.redis_client:
            try:
                return await self.redis_client.get(key)
            except Exception as e:
                logger.error(f"Redis get error for key '{key}': {str(e)}")
        return self._fallback_db.get(key)

    async def set(self, key: str, value: str, expire: int = 86400) -> bool:
        """Sets cache key with default expiration of 24 hours."""
        if self.redis_client:
            try:
                await self.redis_client.set(key, value, ex=expire)
                return True
            except Exception as e:
                logger.error(f"Redis set error for key '{key}': {str(e)}")
        self._fallback_db[key] = value
        return True

    async def get_json(self, key: str) -> Optional[Any]:
        data = await self.get(key)
        if data:
            try:
                return json.loads(data)
            except Exception:
                pass
        return None

    async def set_json(self, key: str, value: Any, expire: int = 86400) -> bool:
        try:
            serialized = json.dumps(value)
            return await self.set(key, serialized, expire)
        except Exception as e:
            logger.error(f"JSON serialization error for cache: {str(e)}")
            return False

cache_manager = RedisCacheManager()
