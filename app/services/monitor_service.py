"""Monitor service — HTTP health checks for all CrossWave services."""

import asyncio
import time

SERVICES = [
    {"name": "polsia-fork", "url": "http://localhost:8001/api/v1/health", "label": "Polsia Fork (AI Agents)"},
    {"name": "crosswave",     "url": "http://localhost:9999/health",           "label": "CrossWave (Website)"},
    {"name": "crossblog",     "url": "http://localhost:8002/health",           "label": "CrossBlog (80 Posts)"},
    {"name": "hq-bridge",     "url": "http://localhost:13001/health",          "label": "CrossWave HQ (Bridge)"},
]

HEADERS = {"User-Agent": "CrossWave-Monitor/1.0"}


async def check_service(
    name: str, url: str, timeout: int = 5
) -> dict:
    """Check a single service's health endpoint. Returns result dict."""
    import httpx

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=HEADERS)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "service": name,
            "status": "up" if resp.is_success else "degraded",
            "http_status": resp.status_code,
            "response_time_ms": elapsed_ms,
            "error": "",
        }
    except httpx.TimeoutException:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "service": name,
            "status": "down",
            "http_status": 0,
            "response_time_ms": elapsed_ms,
            "error": "timeout",
        }
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "service": name,
            "status": "down",
            "http_status": 0,
            "response_time_ms": elapsed_ms,
            "error": str(e)[:120],
        }


async def check_all_services(timeout: int = 5) -> list[dict]:
    """Check all configured services in parallel. Returns list of result dicts."""
    tasks = [check_service(s["name"], s["url"], timeout) for s in SERVICES]
    return await asyncio.gather(*tasks)


def service_label(name: str) -> str:
    """Get human-readable label for a service name."""
    for s in SERVICES:
        if s["name"] == name:
            return s["label"]
    return name


def summarize_results(results: list[dict]) -> dict:
    """Aggregate check results into a summary dict."""
    up = sum(1 for r in results if r["status"] == "up")
    degraded = sum(1 for r in results if r["status"] == "degraded")
    down = sum(1 for r in results if r["status"] == "down")
    avg_ms = 0
    if results:
        valid = [r["response_time_ms"] for r in results if r["response_time_ms"] > 0]
        avg_ms = round(sum(valid) / len(valid)) if valid else 0
    return {
        "total": len(results),
        "up": up,
        "degraded": degraded,
        "down": down,
        "avg_response_time_ms": avg_ms,
        "all_up": up == len(results),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
