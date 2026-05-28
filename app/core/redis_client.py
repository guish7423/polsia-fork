"""Async Redis connection with lazy import."""

from app.config import settings

_redis = None


async def get_redis():
    """Get or create the async Redis connection."""
    global _redis
    if _redis is None:
        import redis.asyncio as redis

        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis
