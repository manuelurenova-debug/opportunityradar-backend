"""
OpportunityRadar — Telegram notifier

Sends an alert to Telegram when a high-score opportunity is found.
Uses urllib (stdlib only, no extra dependencies).
"""

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
ALERT_MIN_SCORE    = int(os.getenv("ALERT_MIN_SCORE", "60"))
DASHBOARD_URL      = os.getenv("DASHBOARD_URL", "").rstrip("/")

CATEGORY_EMOJI = {
    "PROBLEM":              "🔴",
    "FEATURE_REQUEST":      "🔵",
    "COMPETITOR_COMPLAINT": "🟠",
    "TREND":                "🟢",
    "OTHER":                "⚪",
}


def _send_telegram(text: str) -> bool:
    """Sends a message via Telegram Bot API. Returns True on success."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("  ⚠️  Telegram not configured (missing token or chat_id)")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result.get("ok", False)
    except Exception as e:
        print(f"  ⚠️  Telegram API error: {e}")
        return False


def format_alert(opportunity: dict) -> str:
    """Formats an opportunity dict into a Telegram HTML message."""
    category  = opportunity.get("category", "OTHER")
    emoji     = CATEGORY_EMOJI.get(category, "⚪")
    score     = opportunity.get("total_score", 0)
    title     = opportunity.get("title", "")
    subreddit = opportunity.get("subreddit", "")
    upvotes   = opportunity.get("upvotes", 0)
    comments  = opportunity.get("num_comments", 0)
    url       = opportunity.get("url", "")
    opp_id    = opportunity.get("id", "")

    eng = opportunity.get("engagement_score", 0)
    rec = opportunity.get("recurrence_score", 0)
    urg = opportunity.get("urgency_score", 0)

    # Urgency keywords from evidence
    evidence = opportunity.get("evidence", {}) or {}
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except Exception:
            evidence = {}
    keywords = evidence.get("urgency_keywords", [])
    keywords_str = ", ".join(f'"{k}"' for k in keywords) if keywords else "—"

    # Score bar (visual)
    filled = round(score / 5)
    bar = "█" * filled + "░" * (20 - filled)

    # Dashboard link (only if URL is configured)
    dashboard_line = ""
    if DASHBOARD_URL and opp_id:
        dashboard_line = f'\n🖥 <a href="{DASHBOARD_URL}/opportunity/{opp_id}">Ver en dashboard</a>'

    # Reddit link
    reddit_line = f'\n🔗 <a href="{url}">Ver post en Reddit</a>' if url else ""

    message = (
        f"🎯 <b>Nueva oportunidad — Score {score}/100</b>\n"
        f"<code>{bar}</code>\n"
        f"\n"
        f"{emoji} <b>{category.replace('_', ' ')}</b> · r/{subreddit}\n"
        f"📌 <i>{title}</i>\n"
        f"\n"
        f"📊 Engagement: {eng:.1f} · Recurrence: {rec:.1f} · Urgency: {urg:.1f}\n"
        f"👆 {upvotes:,} upvotes · {comments:,} comentarios\n"
        f"🔑 Signals: {keywords_str}"
        f"{dashboard_line}"
        f"{reddit_line}"
    )

    return message


def should_notify(opportunity: dict) -> bool:
    """Returns True if this opportunity meets the alert threshold."""
    return (
        not opportunity.get("notified", False)
        and opportunity.get("total_score", 0) >= ALERT_MIN_SCORE
    )


def notify_opportunity(opportunity: dict) -> bool:
    """
    Sends a Telegram alert if the opportunity meets the threshold.
    Returns True if the alert was sent successfully.
    """
    if not should_notify(opportunity):
        return False

    text = format_alert(opportunity)
    success = _send_telegram(text)

    if success:
        print(f"  📨 Telegram alert sent (score {opportunity.get('total_score')})")

    return success
