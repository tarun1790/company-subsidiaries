import asyncio
import time
from functools import wraps
from app.core.logging import logger

def retry_with_backoff(retries=3, backoff_seconds=2.0, exceptions=(Exception,)):
    """Asynchronous decorator to retry transient failures with exponential backoff."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt > retries:
                        logger.error(f"Retry limits exceeded for {func.__name__} after {retries} retries. Error: {str(e)}")
                        raise e
                    
                    # Calculate backoff: backoff_seconds * (2 ** (attempt - 1))
                    sleep_time = backoff_seconds * (2 ** (attempt - 1))
                    logger.warning(
                        f"Attempt {attempt} failed for {func.__name__} due to: {str(e)}. "
                        f"Retrying in {sleep_time:.2f} seconds..."
                    )
                    await asyncio.sleep(sleep_time)
        return wrapper
    return decorator
