"""API key authentication via X-API-Key header."""

from fastapi import Header, HTTPException

from app.config import settings


async def verify_api_key(
    x_api_key: str = Header(None, alias="X-API-Key"),
) -> str:
    """Verify the X-API-Key header matches the configured key."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key
