"""Email notification service — SMTP delivery for pipeline events.

Triggers: proposal sent, proposal accepted, proposal rejected,
deliverables ready.  Each notification includes a direct link
to /quote/{view_token} so the customer never needs to search.
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import settings

logger = logging.getLogger(__name__)

_BASE_URL: str = ""


def _configure() -> tuple[str, int, str, str, str, str]:
    """Return (host, port, user, password, from_addr, from_name)."""
    return (
        settings.smtp_host,
        settings.smtp_port,
        settings.smtp_user,
        settings.smtp_password,
        settings.smtp_from_email,
        settings.smtp_from_name,
    )


def _make_html(subject: str, body_html: str) -> str:
    """Wrap body_html into a minimal but branded HTML email."""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08)">
<tr><td style="padding:32px 32px 0;text-align:center;background:linear-gradient(135deg,#1a1a2e,#16213e)">
<img src="https://crosswave.app/logo.png" alt="CrossWave" width="40" height="40" style="border-radius:8px">
<h1 style="color:#fff;font-size:20px;margin:12px 0 0">{subject}</h1>
</td></tr>
<tr><td style="padding:32px;color:#333;font-size:14px;line-height:1.7">
{body_html}
</td></tr>
<tr><td style="padding:16px 32px;background:#fafafa;border-top:1px solid#eee;text-align:center;color:#999;font-size:12px">
CrossWave 🌊 · <a href="https://crosswave.app" style="color:#667eea">crosswave.app</a>
</td></tr>
</table>
</td></tr></table>
</body>
</html>"""


# ── Template helpers ────────────────────────────────────────────────


def _proposal_sent_html(name: str, view_url: str, amount: str,
                        summary: str, order_title: str) -> str:
    return f"""
<p>Hi {name},</p>
<p>感谢您对 <strong>{order_title}</strong> 的询价！我们已为您生成定制化报价方案。</p>
<table role="presentation" width="100%" cellpadding="12" cellspacing="0"
       style="background:#f8f9ff;border-radius:8px;margin:20px 0">
<tr><td style="text-align:center">
<div style="font-size:28px;font-weight:700;color:#1a1a2e">{amount}</div>
<div style="color:#666;font-size:13px">预估价格</div>
</td></tr>
</table>
<p style="color:#555">{summary}</p>
<p style="text-align:center;margin:28px 0">
<a href="{view_url}" style="display:inline-block;padding:12px 32px;border-radius:8px;
background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;text-decoration:none;font-weight:600">
📄 查看完整报价方案
</a>
</p>
<p style="color:#999;font-size:13px">方案有效期为 7 天。如有任何疑问，随时回复此邮件。</p>
"""


def _proposal_accepted_html(name: str, view_url: str, order_title: str) -> str:
    return f"""
<p>Hi {name}，</p>
<p>太棒了！您已接受 <strong>{order_title}</strong> 的报价方案 🎉</p>
<p>我们的部署团队已收到通知，正在为您准备交付环境。</p>
<p style="text-align:center;margin:28px 0">
<a href="{view_url}" style="display:inline-block;padding:12px 32px;border-radius:8px;
background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;text-decoration:none;font-weight:600">
📊 查看项目进度
</a>
</p>
<p style="color:#999;font-size:13px">我们会在 1-2 个工作日内完成部署并通知您。</p>
"""


def _deliverables_ready_html(name: str, view_url: str, order_title: str) -> str:
    return f"""
<p>Hi {name}，</p>
<p><strong>{order_title}</strong> 的部署交付已完成 ✅</p>
<p>所有交付物已准备就绪，您可以随时查看和下载。</p>
<p style="text-align:center;margin:28px 0">
<a href="{view_url}" style="display:inline-block;padding:12px 32px;border-radius:8px;
background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;text-decoration:none;font-weight:600">
📦 查看交付物
</a>
</p>
<p style="color:#999;font-size:13px">如有问题，请随时联系我们的技术支持团队。</p>
"""


def _internal_notification_html(event: str, details: str, view_url: str) -> str:
    """Internal team notification (proposal accepted/rejected)."""
    emoji = "✅" if "accepted" in event or "won" in event else "ℹ️"
    return f"""
<p style="font-size:16px;font-weight:600">{emoji} {event}</p>
<p style="color:#555">{details}</p>
<p><a href="{view_url}" style="color:#667eea">查看详情 →</a></p>
"""


# ── Public API ──────────────────────────────────────────────────────


def send_proposal_sent(name: str, email: str, view_url: str,
                       amount: str, summary: str, order_title: str) -> bool:
    """Notify customer that their proposal is ready."""
    return _send(
        to=email,
        subject=f"您的报价方案已就绪 — CrossWave",
        html=_proposal_sent_html(name, view_url, amount, summary, order_title),
    )


def send_proposal_accepted(name: str, email: str, view_url: str,
                           order_title: str) -> bool:
    """Notify customer that they accepted the proposal."""
    return _send(
        to=email,
        subject=f"项目已启动 🚀 — CrossWave",
        html=_proposal_accepted_html(name, view_url, order_title),
    )


def send_deliverables_ready(name: str, email: str, view_url: str,
                            order_title: str) -> bool:
    """Notify customer that deliverables are ready."""
    return _send(
        to=email,
        subject=f"交付完成 ✅ — CrossWave",
        html=_deliverables_ready_html(name, view_url, order_title),
    )


def send_internal_notification(event: str, details: str,
                               view_url: str, to: str | None = None) -> bool:
    """Notify internal team (falls back to smtp_from_email)."""
    return _send(
        to=to or settings.smtp_from_email,
        subject=f"[HQ] {event}",
        html=_internal_notification_html(event, details, view_url),
    )


# ── Core send ───────────────────────────────────────────────────────


def _send(to: str, subject: str, html: str) -> bool:
    """Low-level send.  Returns True on success, False on any error."""
    host, port, user, password, from_addr, from_name = _configure()
    if not host:
        logger.warning("SMTP not configured — skipping email to %s", to)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = to
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to, exc)
        return False
