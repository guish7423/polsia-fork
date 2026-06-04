"""Lightweight HTTP MCP tool executor — simplified JSON-RPC over HTTP."""

from __future__ import annotations

import json
import logging

import httpx

logger = logging.getLogger(__name__)


class MCPClient:
    """Lightweight HTTP MCP tool executor.

    POSTs JSON params to a configured endpoint and returns the JSON response.
    Supports optional header-based auth.
    """

    async def call_tool(
        self,
        endpoint: str,
        params: dict,
        auth: dict | None = None,
        timeout: int = 30,
    ) -> dict:
        """POST *params* to *endpoint* and return the parsed JSON response.

        Args:
            endpoint: Target MCP server URL.
            params: JSON-serialisable parameters dict.
            auth: Optional auth config, e.g. ``{"type": "header", "key": "Authorization", "value": "Bearer xxx"}``.
            timeout: Request timeout in seconds.

        Returns:
            Parsed JSON response dict.

        Raises:
            httpx.HTTPError: On network / HTTP errors.
        """
        headers = {"Content-Type": "application/json"}
        if auth and auth.get("type") == "header":
            key = auth.get("key", "")
            value = auth.get("value", "")
            if key:
                headers[key] = value

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(endpoint, json=params, headers=headers)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "application/json" in content_type:
                return resp.json()
            # Fallback: try to parse text body as JSON
            try:
                return json.loads(resp.text)
            except (json.JSONDecodeError, ValueError):
                return {"result": resp.text}
