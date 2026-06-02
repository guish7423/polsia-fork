"""Weekly report service — cross-platform KPI aggregation + HTML report generation.

Queries Polsia Fork's SQLite for all KPIs, generates HTML,
and optionally sends via email_service.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.email_service import _send as send_email_raw

logger = logging.getLogger(__name__)


async def _scalar(db: AsyncSession, query: str, params: dict | None = None) -> int:
    """Helper: run raw SQL, return first column of first row as int."""
    result = await db.execute(text(query), params or {})
    return result.scalar() or 0


async def generate_report_data(db: AsyncSession) -> dict:
    """Query Polsia DB for weekly KPI snapshot."""
    now = datetime.now()
    week_ago = (now - timedelta(days=7)).isoformat()

    # MRR latest snapshot
    rev_row = (
        await db.execute(
            text(
                "SELECT mrr_cents, arr_cents, active_subscribers, snapshot_date "
                "FROM revenue_snapshots ORDER BY snapshot_date DESC LIMIT 1"
            )
        )
    ).fetchone()

    # MRR a week ago
    rev_ago_row = (
        await db.execute(
            text(
                "SELECT mrr_cents FROM revenue_snapshots "
                "WHERE snapshot_date <= date('now', '-7 days') "
                "ORDER BY snapshot_date DESC LIMIT 1"
            )
        )
    ).fetchone()

    mrr_current = (rev_row[0] or 0) / 100.0 if rev_row else 0
    mrr_ago = (rev_ago_row[0] or 0) / 100.0 if rev_ago_row else 0

    # Tasks
    total_tasks = await _scalar(db, "SELECT COUNT(*) FROM tasks")
    done_tasks = await _scalar(
        db, "SELECT COUNT(*) FROM tasks WHERE status IN ('done','completed')"
    )
    failed_tasks = await _scalar(
        db, "SELECT COUNT(*) FROM tasks WHERE status='failed'"
    )
    pending_tasks = await _scalar(
        db, "SELECT COUNT(*) FROM tasks WHERE status='pending'"
    )
    recent_tasks = await _scalar(
        db, "SELECT COUNT(*) FROM tasks WHERE created_at >= :w", {"w": week_ago}
    )

    # Leads
    total_leads = await _scalar(db, "SELECT COUNT(*) FROM leads")
    new_leads = await _scalar(db, "SELECT COUNT(*) FROM leads WHERE status='new'")
    won_leads = await _scalar(db, "SELECT COUNT(*) FROM leads WHERE status='won'")
    recent_leads = await _scalar(
        db, "SELECT COUNT(*) FROM leads WHERE created_at >= :w", {"w": week_ago}
    )

    # External orders
    total_ext = await _scalar(db, "SELECT COUNT(*) FROM external_orders")
    pending_ext = await _scalar(
        db,
        "SELECT COUNT(*) FROM external_orders WHERE status IN ('scanned','pending')",
    )
    accepted_ext = await _scalar(
        db, "SELECT COUNT(*) FROM external_orders WHERE status='accepted'"
    )

    # Proposals
    total_proposals = await _scalar(db, "SELECT COUNT(*) FROM proposals")
    sent_proposals = await _scalar(
        db, "SELECT COUNT(*) FROM proposals WHERE status='sent'"
    )
    won_proposals = await _scalar(
        db, "SELECT COUNT(*) FROM proposals WHERE status='won'"
    )

    # Activity
    recent_activity = await _scalar(
        db, "SELECT COUNT(*) FROM activity_log WHERE created_at >= :w", {"w": week_ago}
    )
    agent_runs = await _scalar(
        db,
        "SELECT COUNT(*) FROM agent_runs WHERE started_at >= :w",
        {"w": week_ago},
    )

    # Revenue trend (30 days)
    rev_history = (
        await db.execute(
            text(
                "SELECT snapshot_date, mrr_cents FROM revenue_snapshots "
                "WHERE snapshot_date >= date('now', '-30 days') ORDER BY snapshot_date"
            )
        )
    ).fetchall()

    # Agent performance
    agents_data = (
        await db.execute(
            text(
                "SELECT agent_type, COUNT(*) as cnt "
                "FROM tasks WHERE status IN ('done','completed') "
                "GROUP BY agent_type ORDER BY cnt DESC LIMIT 10"
            )
        )
    ).fetchall()

    return {
        "generated_at": now.isoformat(),
        "period": f"{(now - timedelta(days=7)).date()} ~ {now.date()}",
        "mrr": {
            "current": round(mrr_current, 2),
            "arr": round((rev_row[1] or 0) / 100.0, 2) if rev_row else 0,
            "subscribers": rev_row[2] or 0 if rev_row else 0,
            "last_week": round(mrr_ago, 2),
            "growth": round(mrr_current - mrr_ago, 2),
            "growth_pct": round(
                ((mrr_current - mrr_ago) / mrr_ago * 100) if mrr_ago > 0 else 0, 1
            ),
        },
        "tasks": {
            "total": total_tasks,
            "done": done_tasks,
            "failed": failed_tasks,
            "pending": pending_tasks,
            "completion_rate": round(
                done_tasks / total_tasks * 100, 1
            ) if total_tasks > 0 else 0,
            "this_week": recent_tasks,
        },
        "leads": {
            "total": total_leads,
            "new": new_leads,
            "won": won_leads,
            "this_week": recent_leads,
            "conversion_rate": round(
                won_leads / total_leads * 100, 1
            ) if total_leads > 0 else 0,
        },
        "external_orders": {
            "total": total_ext,
            "pending": pending_ext,
            "accepted": accepted_ext,
        },
        "proposals": {"total": total_proposals, "sent": sent_proposals, "won": won_proposals},
        "activity": {"this_week": recent_activity, "agent_runs_this_week": agent_runs},
        "revenue_trend_30d": [
            {"date": r[0], "mrr": round(r[1] / 100.0, 2)} for r in rev_history
        ],
        "top_agents": [
            {"agent_type": r[0], "completed_tasks": r[1]} for r in agents_data
        ],
    }


def generate_html_report(data: dict) -> str:
    """Generate a branded HTML report from report data."""
    m = data["mrr"]
    t = data["tasks"]
    l = data["leads"]
    o = data["external_orders"]
    p = data["proposals"]
    a = data["activity"]
    growth_icon = "📈" if m["growth"] >= 0 else "📉"

    # Top agents bar
    agent_bars = ""
    for ag in data.get("top_agents", []):
        w = min(ag["completed_tasks"] * 20, 100)
        agent_bars += f"""
        <tr>
            <td style="padding:4px 8px;color:#666">{ag['agent_type']}</td>
            <td style="padding:4px 8px">
                <div style="background:#e8ecf4;border-radius:4px;height:20px;overflow:hidden">
                    <div style="height:100%;width:{w}%;background:linear-gradient(90deg,#667eea,#764ba2);border-radius:4px;text-align:right;padding-right:6px;color:#fff;font-size:11px;line-height:20px">{ag['completed_tasks']}</div>
                </div>
            </td>
        </tr>"""

    rev_trend_rows = ""
    for rv in data.get("revenue_trend_30d", []):
        rev_trend_rows += f"<tr><td style='padding:2px 8px;color:#666;font-size:12px'>{rv['date']}</td><td style='padding:2px 8px;color:#333;font-size:12px;text-align:right'>${rv['mrr']:.2f}</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8">
<style>
  body {{ margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif }}
  .container {{ max-width:640px;margin:0 auto;padding:24px 16px }}
  .card {{ background:#fff;border-radius:12px;padding:24px;margin:16px 0;box-shadow:0 1px 6px rgba(0,0,0,.06) }}
  .kpi-row {{ display:flex;gap:12px;flex-wrap:wrap }}
  .kpi {{ flex:1;min-width:120px;text-align:center;padding:16px;background:#f8f9ff;border-radius:8px }}
  .kpi .value {{ font-size:24px;font-weight:700;color:#1a1a2e }}
  .kpi .label {{ font-size:12px;color:#999;margin-top:4px }}
  table {{ width:100%;border-collapse:collapse }}
  h2 {{ font-size:18px;color:#1a1a2e;margin:0 0 12px }}
  .header {{ background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:32px;text-align:center;border-radius:12px 12px 0 0 }}
  .header h1 {{ margin:0;font-size:22px }}
  .header p {{ margin:8px 0 0;opacity:.8;font-size:13px }}
  .footer {{ text-align:center;padding:24px;color:#999;font-size:12px }}
</style></head>
<body>
<div class="container">
<div class="header">
  <h1>📊 CrossWave 周报</h1>
  <p>{data['period']} · 生成 {data['generated_at'][:19]}</p>
</div>

<div class="card">
  <h2>💰 收入</h2>
  <div class="kpi-row">
    <div class="kpi"><div class="value">${m['current']:.2f}</div><div class="label">MRR</div></div>
    <div class="kpi"><div class="value">${m['arr']:.2f}</div><div class="label">ARR</div></div>
    <div class="kpi"><div class="value">{m['subscribers']}</div><div class="label">订阅</div></div>
    <div class="kpi"><div class="value">{growth_icon} ${abs(m['growth']):.2f}</div><div class="label">周增长 ({m['growth_pct']}%)</div></div>
  </div>
</div>

<div class="card">
  <h2>✅ 任务</h2>
  <div class="kpi-row">
    <div class="kpi"><div class="value">{t['total']}</div><div class="label">总计</div></div>
    <div class="kpi"><div class="value" style="color:#22c55e">{t['done']}</div><div class="label">完成</div></div>
    <div class="kpi"><div class="value" style="color:#ef4444">{t['failed']}</div><div class="label">失败</div></div>
    <div class="kpi"><div class="value">{t['pending']}</div><div class="label">待处理</div></div>
  </div>
  <p style="text-align:center;color:#666;font-size:14px">完成率 <strong>{t['completion_rate']}%</strong> · 本周新增 <strong>{t['this_week']}</strong></p>
</div>

<div class="card">
  <h2>👥 线索 & 订单</h2>
  <div class="kpi-row">
    <div class="kpi"><div class="value">{l['total']}</div><div class="label">线索</div></div>
    <div class="kpi"><div class="value" style="color:#22c55e">{l['won']}</div><div class="label">成交</div></div>
    <div class="kpi"><div class="value">{o['total']}</div><div class="label">外部订单</div></div>
    <div class="kpi"><div class="value">{p['sent']}</div><div class="label">提案已发</div></div>
  </div>
  <p style="text-align:center;color:#666;font-size:14px">线索转化率 <strong>{l['conversion_rate']}%</strong> · 本周新增线索 <strong>{l['this_week']}</strong> · 已接受提案 <strong>{p['won']}</strong></p>
</div>

<div class="card">
  <h2>🤖 Agent 排行</h2>
  <table>{agent_bars}</table>
</div>

<div class="card">
  <h2>🔄 活动</h2>
  <p style="text-align:center;color:#666">本周活动记录 <strong>{a['this_week']}</strong> · Agent 执行 <strong>{a['agent_runs_this_week']}</strong> 次</p>
</div>

<div class="card">
  <h2>📈 30天收入趋势</h2>
  <table>{rev_trend_rows}</table>
</div>

<div class="footer">
  CrossWave 🌊 · <a href="https://crosswave.app" style="color:#667eea">crosswave.app</a><br>
  由 CrossWave HQ 自动生成
</div>
</div>
</body>
</html>"""


async def generate_and_email_report(db: AsyncSession) -> dict | None:
    """Generate weekly report and email to internal team."""
    data = await generate_report_data(db)
    html = generate_html_report(data)

    m = data["mrr"]
    t = data["tasks"]
    l = data["leads"]
    summary = (
        f"MRR ${m['current']:.2f} ({m['growth_pct']:+.1f}%) | "
        f"任务 {t['done']}/{t['total']} ({t['completion_rate']}%) | "
        f"线索 {l['total']} ({l['conversion_rate']}% 转化) | "
        f"外部订单 {data['external_orders']['total']}"
    )

    # Send via email_service raw send
    sent = False
    if settings.smtp_from_email:
        sent = send_email_raw(
            to=settings.smtp_from_email,
            subject=f"📊 CrossWave 周报 — {data['period']}",
            html=html,
        )
    else:
        logger.warning("SMTP not configured — skipping weekly report email")

    # Save to DB as report record
    try:
        await db.execute(
            text(
                "INSERT INTO weekly_reports (period_start, period_end, summary, html_content, recipient_count) "
                "VALUES (:start, :end, :summary, :html, :rcpt)"
            ),
            {
                "start": data["period"].split(" ~ ")[0],
                "end": data["period"].split(" ~ ")[1],
                "summary": summary,
                "html": html,
                "rcpt": 1 if sent else 0,
            },
        )
        await db.commit()
    except Exception as exc:
        logger.warning("Failed to save weekly report to DB: %s", exc)
        await db.rollback()

    logger.info(
        "Weekly report generated. Period: %s. Email sent: %s",
        data["period"],
        sent,
    )
    return data
