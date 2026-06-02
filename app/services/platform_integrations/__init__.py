"""Platform integrations — credential-gated connectors to external marketplaces.

Each module exposes a standard interface:
    async def search_orders() -> list[dict]
        Returns list of job/order dicts with keys:
            title, description, platform, tags, salary_min, salary_max, source_url

Modules are gated by a REQUIRED_ENV_VARS check:
    is_available() -> bool
"""

from .upwork_mcp import UpworkMCPIntegration
from .zhubajie_api import ZhubajieAPIIntegration
