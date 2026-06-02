"""Upwork MCP integration — connects to Upwork's GraphQL API via MCP server.

REQUIRED ENV:
    UPWORK_CLIENT_ID     — OAuth Client ID from Upwork Developer Portal
    UPWORK_CLIENT_SECRET — OAuth Client Secret

SETUP:
    1. Go to https://www.upwork.com/developer/keys/apply
    2. Create a new API application
    3. Note your Client ID and Client Secret
    4. Set UPWORK_CLIENT_ID + UPWORK_CLIENT_SECRET env vars
    5. Run: npx @furkankoykiran/upwork-mcp auth
    6. Restart Polsia Fork — integration auto-activates

The MCP server provides 18 tools including search_jobs, submit_proposal,
list_proposals, list_contracts, get_profile, etc.

This wrapper calls the MCP server's search_jobs tool via subprocess.
"""

import json
import os
from typing import Any

REQUIRED_ENV_VARS = ["UPWORK_CLIENT_ID", "UPWORK_CLIENT_SECRET"]
PLATFORM_NAME = "upwork-mcp"

# Categories/keywords to search on Upwork
UPWORK_SEARCH_QUERIES = [
    "FastAPI Python backend development",
    "Docker Kubernetes DevOps deployment",
    "React Next.js fullstack development",
    "CI/CD pipeline automation",
    "API integration development",
    "Cloud infrastructure AWS GCP",
    "NocoBase plugin development",
    "AI chatbot integration",
]

SEARCH_CONFIG = {
    "max_results": 20,
    "budget_min": 200,  # $ minimum — skip micro-gigs
    "sort": "recency",  # newest first
}


def is_available() -> bool:
    """Check if Upwork integration can be used (credentials configured)."""
    return all(os.getenv(var) for var in REQUIRED_ENV_VARS)


async def search_orders() -> list[dict]:
    """Search Upwork for relevant jobs via MCP server.
    
    Returns list of job dicts compatible with order_scanner_service._save_jobs().
    
    Note: This requires the Upwork MCP server npm package installed globally:
        npm install -g @furkankoykiran/upwork-mcp
    
    And OAuth authentication run at least once:
        export UPWORK_CLIENT_ID="..."
        export UPWORK_CLIENT_SECRET="..."
        npx @furkankoykiran/upwork-mcp auth
    """
    if not is_available():
        return []

    jobs: list[dict] = []
    
    try:
        import asyncio
        
        for query in UPWORK_SEARCH_QUERIES[:3]:  # limit to 3 queries per scan
            result = await _run_mcp_search(query)
            if result:
                jobs.extend(result)
        
        # Deduplicate by title
        seen = set()
        unique_jobs = []
        for job in jobs:
            key = job["title"].lower().strip()
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)
        
        return unique_jobs[:SEARCH_CONFIG["max_results"]]
    
    except Exception as e:
        print(f"[upwork-mcp] Integration failed: {e}")
        return []


async def _run_mcp_search(query: str) -> list[dict]:
    """Execute a single search via Upwork MCP CLI subprocess."""
    import asyncio
    
    try:
        proc = await asyncio.create_subprocess_exec(
            "npx", "-y", "@furkankoykiran/upwork-mcp",
            "--tool", "search_jobs",
            "--args", json.dumps({
                "query": query,
                "budget_min": SEARCH_CONFIG["budget_min"],
                "sort": SEARCH_CONFIG["sort"],
            }),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ},
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            proc.kill()
            print(f"[upwork-mcp] Search timeout for: {query}")
            return []
        
        if proc.returncode != 0:
            print(f"[upwork-mcp] Search failed (rc={proc.returncode}): {stderr.decode()[:200]}")
            return []
        
        raw = stdout.decode()
        results = json.loads(raw) if raw.strip() else []
        
        formatted = []
        for job in results if isinstance(results, list) else [results]:
            if not isinstance(job, dict):
                continue
            title = (job.get("title") or job.get("job_title") or "").strip()
            if not title:
                continue
            
            formatted.append({
                "title": title,
                "description": (
                    job.get("description") or 
                    job.get("snippet") or 
                    job.get("job_description", "")
                )[:1000],
                "platform": PLATFORM_NAME,
                "tags": [
                    t.get("name", t) if isinstance(t, dict) else str(t)
                    for t in (job.get("skills") or job.get("tags", []) or [])
                ][:8],
                "salary_min": job.get("budget", {}).get("min") if isinstance(job.get("budget"), dict) else job.get("budget_min"),
                "salary_max": job.get("budget", {}).get("max") if isinstance(job.get("budget"), dict) else job.get("budget_max"),
                "source_url": job.get("url") or job.get("job_url", ""),
            })
        
        return formatted
    
    except Exception as e:
        print(f"[upwork-mcp] _run_mcp_search error: {e}")
        return []
