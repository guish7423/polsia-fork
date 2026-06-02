"""猪八戒开放平台 API integration — connects to zbj.com open platform.

REQUIRED ENV:
    ZHUBAJIE_APP_KEY     — App Key from 猪八戒开放平台
    ZHUBAJIE_APP_SECRET  — App Secret

SETUP:
    1. Go to https://open.zbj.com/ → 注册开发者
    2. Create a new application
    3. Note your App Key and App Secret
    4. Set ZHUBAJIE_APP_KEY + ZHUBAJIE_APP_SECRET env vars
    5. Restart Polsia Fork — integration auto-activates

猪八戒 open API endpoints (subject to change):
    GET /api/demand/list     — browse demand/orders
    GET /api/demand/detail   — order detail
    GET /api/user/info       — user info
    POST /api/demand/bid     — submit bid

This wrapper uses httpx to call the open REST API with signature auth.
"""

import hashlib
import json
import os
import time
from typing import Any

import httpx

REQUIRED_ENV_VARS = ["ZHUBAJIE_APP_KEY", "ZHUBAJIE_APP_SECRET"]
PLATFORM_NAME = "zhubajie"

# API base
ZHUBAJIE_API_BASE = os.getenv("ZHUBAJIE_API_BASE", "https://open.zbj.com/api")

# Search categories relevant to CrossDeploy services
SEARCH_CATEGORIES = [
    {"cat_id": 1, "name": "网站开发"},
    {"cat_id": 2, "name": "小程序开发"},
    {"cat_id": 3, "name": "AI应用开发"},
    {"cat_id": 4, "name": "系统运维"},
    {"cat_id": 5, "name": "API开发"},
]


def is_available() -> bool:
    """Check if 猪八戒 integration can be used (credentials configured)."""
    return all(os.getenv(var) for var in REQUIRED_ENV_VARS)


def _sign_request(params: dict, app_secret: str) -> str:
    """Generate signature per 猪八戒 open API spec.
    
    Sorts params alphabetically, concatenates key=value,
    appends secret, MD5 hashes.
    """
    sorted_keys = sorted(params.keys())
    raw = "".join(f"{k}{params[k]}" for k in sorted_keys)
    raw += app_secret
    return hashlib.md5(raw.encode()).hexdigest()


async def _api_get(endpoint: str, params: dict | None = None) -> dict:
    """Call 猪八戒 open API with signature auth."""
    app_key = os.getenv("ZHUBAJIE_APP_KEY", "")
    app_secret = os.getenv("ZHUBAJIE_APP_SECRET", "")
    
    base_params = {
        "app_key": app_key,
        "timestamp": str(int(time.time())),
        "format": "json",
        "v": "1.0",
    }
    if params:
        base_params.update(params)
    
    base_params["sign"] = _sign_request(base_params, app_secret)
    
    url = f"{ZHUBAJIE_API_BASE}/{endpoint.lstrip('/')}"
    
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=base_params)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"[zhubajie] API {endpoint} returned {resp.status_code}")
            return {}


async def search_orders() -> list[dict]:
    """Search 猪八戒 for relevant demand/orders.
    
    Returns list of order dicts compatible with order_scanner_service._save_jobs().
    """
    if not is_available():
        return []
    
    jobs: list[dict] = []
    
    try:
        for cat in SEARCH_CATEGORIES:
            result = await _api_get("demand/list", {
                "cat_id": cat["cat_id"],
                "page_size": 10,
                "page_no": 1,
                "sort": "new",
            })
            
            items = result.get("data", {}).get("list", []) if isinstance(result, dict) else []
            if not items and isinstance(result, list):
                items = result
            
            for item in (items or []):
                if not isinstance(item, dict):
                    continue
                
                title = (item.get("title") or item.get("demand_title") or "").strip()
                if not title:
                    continue
                
                # Price range
                budget_min = item.get("budget_min") or item.get("price_min")
                budget_max = item.get("budget_max") or item.get("price_max")
                
                # Convert CNY to number
                try:
                    budget_min = float(budget_min) if budget_min else None
                except (ValueError, TypeError):
                    budget_min = None
                try:
                    budget_max = float(budget_max) if budget_max else None
                except (ValueError, TypeError):
                    budget_max = None
                
                jobs.append({
                    "title": title,
                    "description": (item.get("description") or item.get("demand_desc", ""))[:1000],
                    "platform": PLATFORM_NAME,
                    "tags": [cat["name"]] + (item.get("tags", []) or []),
                    "salary_min": budget_min,
                    "salary_max": budget_max,
                    "source_url": item.get("url") or item.get("demand_url", ""),
                })
        
        # Deduplicate
        seen = set()
        unique = []
        for j in jobs:
            key = j["title"].lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(j)
        
        return unique[:20]
    
    except Exception as e:
        print(f"[zhubajie] Integration failed: {e}")
        return []
