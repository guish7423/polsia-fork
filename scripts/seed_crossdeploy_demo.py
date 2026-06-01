"""CrossDeploy Demo: simulate full customer lifecycle end-to-end.

Creates 3 real customer journeys through the full pipeline:
  Inquiry → Lead → Convert → ExternalOrder → DeployAgent → Portal

Usage:
  python scripts/seed_crossdeploy_demo.py       # Create demo data
  python scripts/seed_crossdeploy_demo.py --clean  # Clean up demo data first
"""

import asyncio, sys, httpx, os

API_BASE = os.environ.get("POLSIA_API", "http://127.0.0.1:8001")
API_KEY = os.environ.get("POLSIA_API_KEY", "dev-key")
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

DEMO_CUSTOMERS = [
    {
        "name": "李华",
        "email": "lihua@example.com",
        "company": "优创科技",
        "phone": "13800138001",
        "product_interest": "crossdeploy-basic",
        "budget_range": "2000-3000",
        "message": "需要一个 AI 聊天机器人部署到公司官网，单服务 Docker 部署即可，已有域名。",
        "source_page": "/deploy",
        "tier": "basic",
        "expected_price": 2000,
    },
    {
        "name": "Sarah Chen",
        "email": "sarah@techglobal.io",
        "company": "TechGlobal Inc.",
        "phone": "+1-555-0123",
        "product_interest": "crossdeploy-standard",
        "budget_range": "3000-5000",
        "message": "We need full SaaS infrastructure: FastAPI backend + Next.js frontend + PostgreSQL + Redis + CI/CD pipeline. Multi-service Docker Compose. Production-ready with monitoring.",
        "source_page": "/deploy",
        "tier": "standard",
        "expected_price": 3000,
    },
    {
        "name": "张总",
        "email": "zhang@dashu-ai.cn",
        "company": "大数据智能科技",
        "phone": "13900139002",
        "product_interest": "crossdeploy-enterprise",
        "budget_range": "5000-8000",
        "message": "企业级 AI 平台：需要 K8s 集群部署，自动伸缩，多个微服务，Prometheus 监控，Grafana 面板，CI/CD GitOps 流水线。预计 5-8 个微服务。",
        "source_page": "/deploy",
        "tier": "enterprise",
        "expected_price": 5000,
    },
]


async def clean_demo():
    """Remove demo leads and orders."""
    print("🧹 Cleaning demo data...")
    # Get all leads
    r = await client.get(f"{API_BASE}/api/v1/leads")
    if r.status_code == 200:
        for lead in r.json().get("data", []):
            if lead["name"] in [c["name"] for c in DEMO_CUSTOMERS]:
                # Mark as lost (soft delete)
                await client.patch(
                    f"{API_BASE}/api/v1/leads/{lead['id']}/status",
                    headers=HEADERS,
                    json={"status": "lost"},
                )
                print(f"  ✓ Lead #{lead['id']} ({lead['name']}) → lost")

    # Get orders
    r = await client.get(f"{API_BASE}/api/v1/orders/external")
    if r.status_code == 200:
        for order in r.json().get("data", []):
            if any(c["name"] in (order.get("title") or "") for c in DEMO_CUSTOMERS):
                # Can't delete, just note
                print(f"  ⚠ Order #{order['id']} ({order['title'][:40]}...) — exists")
    print("  Done.")


async def seed_demo():
    print("=" * 60)
    print("🌊 CrossDeploy Demo Pipeline — Seeding Full Customer Journey")
    print("=" * 60)

    for i, customer in enumerate(DEMO_CUSTOMERS, 1):
        print(f"\n{'─' * 50}")
        print(f"📋 Customer {i}/3: {customer['name']} ({customer['company']})")
        print(f"   Tier: {customer['tier'].upper()} | Budget: {customer['budget_range']}")
        print(f"{'─' * 50}")

        # Step 1: Create Lead (as if from inquiry form)
        print(f"\n  1/6 📝 Creating lead from inquiry...")
        r = await client.post(
            f"{API_BASE}/api/v1/leads",
            headers=HEADERS,
            json={
                "name": customer["name"],
                "email": customer["email"],
                "company": customer["company"],
                "phone": customer.get("phone"),
                "product_interest": customer["product_interest"],
                "budget_range": customer["budget_range"],
                "message": customer["message"],
                "source_page": customer["source_page"],
                "status": "new",
            },
        )
        if r.status_code == 200:
            lead = r.json()
            lead_id = lead["id"]
            print(f"     ✅ Lead #{lead_id} created: {lead['name']} ({lead['status']})")
        else:
            print(f"     ❌ Failed: {r.status_code} {r.text}")
            continue

        # Step 2: Qualify lead (simulate internal process)
        print(f"  2/6 🔄 Qualifying lead...")
        r = await client.patch(
            f"{API_BASE}/api/v1/leads/{lead_id}/status",
            headers=HEADERS,
            json={"status": "qualified"},
        )
        if r.status_code == 200:
            print(f"     ✅ Lead #{lead_id} → qualified")
        else:
            print(f"     ⚠ {r.status_code}")

        # Step 3: Send proposal
        print(f"  3/6 📄 Sending proposal...")
        r = await client.patch(
            f"{API_BASE}/api/v1/leads/{lead_id}/status",
            headers=HEADERS,
            json={"status": "proposal"},
        )
        if r.status_code == 200:
            print(f"     ✅ Lead #{lead_id} → proposal")
        else:
            print(f"     ⚠ {r.status_code}")

        # Step 4: Convert to order
        print(f"  4/6 🔄 Converting to order (tier: {customer['tier']})...")
        r = await client.post(
            f"{API_BASE}/api/v1/leads/{lead_id}/convert",
            headers=HEADERS,
            json={"tier": customer["tier"]},
        )
        if r.status_code == 200:
            result = r.json()
            order_id = result["order_id"]
            print(f"     ✅ Order #{order_id} created: {result['title'][:50]}... | ¥{customer['expected_price']:,}")
        else:
            print(f"     ❌ Failed: {r.status_code} {r.text}")
            continue

        # Step 5: Assign to DeployAgent and trigger
        print(f"  5/6 🚀 Assigning to DeployAgent and triggering...")

        # Accept the order first
        r = await client.post(
            f"{API_BASE}/api/v1/orders/external/{order_id}/accept",
            headers=HEADERS,
            params={"assigned_agent": "deploy_agent"},
        )
        if r.status_code == 200:
            print(f"     ✅ Order #{order_id} → accepted (assigned to deploy_agent)")
        else:
            print(f"     ⚠ Accept: {r.status_code}")

        # Run demo deploy to generate deployment plan
        r = await client.post(
            f"{API_BASE}/api/v1/orders/external/{order_id}/demo-deploy",
            headers=HEADERS,
        )
        if r.status_code == 200:
            plan = r.json()
            steps = len(plan.get("plan", {}).get("steps", []))
            hours = plan.get("plan", {}).get("estimated_hours", "?")
            print(f"     ✅ Deploy plan generated: {steps} steps, ~{hours}h")
        else:
            print(f"     ⚠ Demo deploy: {r.status_code} {r.text[:100]}")

        # Step 6: Mark as in_progress (verify portal)
        print(f"  6/6 ✅ Verifying HQ visibility...")
        r = await client.get(
            f"{API_BASE}/api/v1/orders/external/{order_id}",
            headers=HEADERS,
        )
        if r.status_code == 200:
            order = r.json()
            print(f"     ✅ Order #{order['id']}: status={order['status']}, score={order.get('score','?')}")
            print(f"     → Portal: /portal/{order['id']}")
        else:
            print(f"     ⚠ Detail: {r.status_code}")

    # Summary
    print(f"\n{'=' * 60}")
    print("📊 DEMO PIPELINE SUMMARY")
    print(f"{'=' * 60}")
    r = await client.get(f"{API_BASE}/api/v1/leads/summary", headers=HEADERS)
    if r.status_code == 200:
        s = r.json()
        print(f"   Leads: {s['total']} total, {s['new_count']} new")
    r = await client.get(f"{API_BASE}/api/v1/orders/external/summary", headers=HEADERS)
    if r.status_code == 200:
        s = r.json()
        print(f"   External orders: {s.get('total', '?')}")
    print(f"\n   ✅ Customer lifecycle complete! Check HQ:")
    print(f"      Leads → /leads")
    print(f"      Orders → /orders")
    print(f"      Deploy → /deploy")
    print(f"      Portal → /portal/1 (or latest order ID)")
    print(f"{'=' * 60}\n")


async def main():
    global client
    async with httpx.AsyncClient(timeout=30) as client:
        if "--clean" in sys.argv:
            await clean_demo()
        else:
            r = await client.get(f"{API_BASE}/api/v1/health", headers=HEADERS)
            if r.status_code != 200:
                print(f"❌ Polsia Fork API not reachable at {API_BASE}")
                print(f"   Response: {r.status_code}")
                return
            print(f"✅ Polsia Fork API OK ({API_BASE})")
            await seed_demo()


if __name__ == "__main__":
    asyncio.run(main())
