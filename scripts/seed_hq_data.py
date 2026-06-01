"""Seed leads and external_orders for CrossWave HQ demo."""
import sqlite3
from datetime import datetime, timedelta
import random
import os

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "polsia.db")
random.seed(42)

def seed():
    db = sqlite3.connect(DB)
    cur = db.cursor()

    # --- Leads ---
    leads_data = [
        ("张伟", "zhangwei@techstar.cn", "北京星辰科技", "CrossBridge", "¥500-1000", "需要将公司技术文档从中文翻译成英文，月均10万字", "new"),
        ("李娜", "lina@aistartup.cn", "上海智元AI", "CrossBlog", "¥1000-3000", "想做AI相关的SEO内容营销，覆盖英文市场", "contacted"),
        ("王磊", "wanglei@shenzhen.dev", "深圳极速科技", "CrossDeploy Basic", "¥2000-5000", "需要部署一个FastAPI应用到阿里云，已有代码", "qualified"),
        ("陈芳", "chenfang@huasheng.cn", "华晟集团", "CrossBridge Pro", "¥3000-5000", "全公司文档本地化，月均50万字，需要API集成", "proposal"),
        ("刘洋", "liuyang@yunwei.cn", "运维科技", "CrossDeploy Enterprise", "¥5000-10000", "K8s集群迁移+CI/CD流水线建设，10+微服务", "negotiation"),
        ("赵雪", "zhaoxue@caogen.cn", "草根创业", "CrossDeploy Basic", "¥2000", "个人博客Next.js转Vercel部署，需要HTTPS域名", "won"),
        ("Tommy Chen", "tommy@siliconvalley.ai", "SiliconAI Inc", "CrossBridge", "$200-500", "Chinese→English localization for AI product documentation", "new"),
        ("Anna Liu", "anna@ecomguru.sg", "EcomGuru SG", "CrossBlog", "$500-1000", "Content marketing for Southeast Asian market, 20 posts/month", "contacted"),
        ("松本隆", "takashi@tokyostartup.jp", "Tokyo Startup KK", "CrossDeploy Standard", "¥3000", "需要日文网站的Docker Compose部署+SSL证书", "qualified"),
        ("Sarah Wong", "sarah@hongkong.digital", "HK Digital Solutions", "CrossDeploy Standard", "$500", "Multi-service deployment with Redis+PostgreSQL, HK server", "new"),
    ]
    cur.execute("DELETE FROM leads")
    for i, (name, email, company, interest, budget, msg, status) in enumerate(leads_data):
        created = datetime.now() - timedelta(days=random.randint(0, 60), hours=random.randint(0, 23))
        cur.execute(
            "INSERT INTO leads (name, email, company, product_interest, budget_range, message, status, source_page, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (name, email, company, interest, budget, msg, status, f"/{'pricing' if i%2==0 else 'deploy'}", created.isoformat(), created.isoformat())
        )
    print(f"Seeded {len(leads_data)} leads")

    # --- External Orders ---
    orders_data = [
        ("部署Flask+PostgreSQL到阿里云ECS", "upwork", "ext-001", "accepted", 3000, 5000, "CNY", 8, "价格合理+技术栈匹配", "deploy_agent"),
        ("Next.js+Strapi网站部署+SSL", "fiverr", "ext-002", "accepted", 2000, 3000, "CNY", 9, "明确需求+预算充足", "order_fulfiller"),
        ("K8s集群迁移服务", "upwork", "ext-003", "scanned", 8000, 15000, "CNY", 6, "大项目但竞争激烈", None),
        ("Python脚本容器化+Docker部署", "fiverr", "ext-004", "scanned", 500, 1000, "CNY", 7, "简单明确", None),
        ("跨境电商网站搭建+部署", "猪八戒", "ext-005", "scanned", 5000, 10000, "CNY", 5, "需求范围模糊", None),
        ("AI模型API封装部署服务", "upwork", "ext-006", "completed", 6000, 8000, "CNY", 9, "高价值+技术匹配度高", "order_fulfiller"),
        ("WordPress迁移到Vercel+Headless", "fiverr", "ext-007", "scanned", 1500, 2500, "CNY", 7, "常见需求", None),
        ("微服务CI/CD流水线搭建", "upwork", "ext-008", "evaluating", 5000, 8000, "CNY", 8, "预算好+长期维护可能", None),
        ("微信小程序后端API部署", "猪八戒", "ext-009", "scanned", 3000, 5000, "CNY", 6, "需要国内服务器", None),
        ("Docker Compose multi-service setup", "upwork", "ext-010", "accepted", 400, 600, "USD", 8, "FastAPI+Redis+PostgreSQL", "deploy_agent"),
        ("Nginx reverse proxy + SSL setup", "fiverr", "ext-011", "completed", 200, 300, "USD", 9, "简单快速交付", "order_fulfiller"),
        ("Full K3s cluster deployment with monitoring", "upwork", "ext-012", "evaluating", 1000, 2000, "USD", 7, "需要英文沟通", None),
    ]
    cur.execute("DELETE FROM external_orders")
    for i, (title, platform, eid, status, bmin, bmax, currency, score, reason, agent) in enumerate(orders_data):
        created = datetime.now() - timedelta(days=random.randint(0, 45), hours=random.randint(0, 23))
        completed = (created + timedelta(hours=random.randint(4, 72))).isoformat() if status == "completed" else None
        cur.execute(
            "INSERT INTO external_orders (title, platform, external_id, status, budget_min, budget_max, currency, description, score, score_reason, assigned_agent, created_at, updated_at, completed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (title, platform, eid, status, bmin, bmax, currency, f"External order: {title}", score, reason, agent, created.isoformat(), created.isoformat(), completed)
        )
    print(f"Seeded {len(orders_data)} external orders")

    # Create a few leads → won → external_orders (conversion pipeline demo)
    won_leads = [l for l in leads_data if l[6] == "won"]
    if won_leads:
        cur.execute("UPDATE leads SET status='won', updated_at=? WHERE status='won'", (datetime.now().isoformat(),))
        print(f"Marked {len(won_leads)} won leads")

    db.commit()
    db.close()
    print(f"\nDB stats:")
    for t in ["leads", "external_orders"]:
        count = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {count} rows")

if __name__ == "__main__":
    seed()
