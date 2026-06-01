"""Market Intelligence Service — collects industry news, competitor intel, opportunity signals."""

import json
import os
import httpx
from datetime import datetime, timezone
from typing import Any

# ─── Search Config ──────────────────────────────────────────────────────────

COMPANY_KEYWORDS = [
    "AI SaaS China global expansion",
    "AI content translation startup",
    "AI agent autonomous business",
    "Chinese SaaS going global 2026",
    "AI部署 自动化运维 创业",
    "AI agent 企业服务 出海",
]

COMPETITOR_QUERIES = [
    "Jasper AI new features 2026",
    "Copy.ai enterprise update",
    "Writesonic product launch",
    "Deploifai AI deployment news",
    "AI translation startup funding",
]

TREND_QUERIES = [
    "AI agent autonomous operation 2026 trend",
    "LLM application SaaS market size 2026",
    "AI content marketing最新趋势",
    "SaaS出海 AI工具 2026",
]

BRIEFINGS_FILE = os.environ.get(
    "BRIEFINGS_FILE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "briefings.json"),
)


# ─── Data Model ──────────────────────────────────────────────────────────────

def ensure_storage():
    os.makedirs(os.path.dirname(BRIEFINGS_FILE), exist_ok=True)
    if not os.path.exists(BRIEFINGS_FILE):
        with open(BRIEFINGS_FILE, "w") as f:
            json.dump([], f)


def save_briefing(briefing: dict):
    ensure_storage()
    briefings = get_briefings()
    briefings.insert(0, briefing)
    with open(BRIEFINGS_FILE, "w") as f:
        json.dump(briefings, f, indent=2, default=str)


def get_briefings(limit: int = 30) -> list[dict]:
    ensure_storage()
    try:
        with open(BRIEFINGS_FILE) as f:
            data = json.load(f)
        return data[:limit]
    except (json.JSONDecodeError, FileNotFoundError):
        return []


# ─── Web Search ──────────────────────────────────────────────────────────────

async def search_exa(query: str, num: int = 3) -> list[dict]:
    """Search via Exa API (if available) or return empty."""
    api_key = os.environ.get("EXA_API_KEY", "")
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.exa.ai/search",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"query": query, "numResults": num, "contents": {"text": True, "length": 500}},
            )
            if resp.status_code == 200:
                data = resp.json()
                return [
                    {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("text", "")[:300]}
                    for r in data.get("results", [])
                ]
    except Exception:
        pass
    return []


async def search_web_fallback(query: str, num: int = 3) -> list[dict]:
    """Fallback: use web_fetch-style search via DuckDuckGo."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            url = f"https://html.duckduckgo.com/html/?q={query}"
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                import re
                snippets = re.findall(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', resp.text)[:num]
                for s in snippets:
                    clean = re.sub(r"<[^>]+>", "", s).strip()
                    results.append({"title": clean, "url": "", "snippet": clean[:200]})
    except Exception:
        pass
    return results


async def gather_intel() -> dict:
    """Run all searches and return structured intelligence."""
    all_sources = COMPANY_KEYWORDS + COMPETITOR_QUERIES + TREND_QUERIES
    all_results = []

    for query in all_sources:
        results = await search_exa(query)
        if not results:
            results = await search_web_fallback(query)
        all_results.extend(results)

    # Deduplicate by title
    seen = set()
    unique = []
    for r in all_results:
        key = r.get("title", "")[:50]
        if key and key not in seen:
            seen.add(key)
            unique.append(r)

    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "total_sources": len(all_sources),
        "total_results": len(unique),
        "results": unique[:25],
        "keywords": COMPANY_KEYWORDS + COMPETITOR_QUERIES,
    }
