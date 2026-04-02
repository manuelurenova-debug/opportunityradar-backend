"""
OpportunityRadar — Weekly Digest

Queries the last 7 days of opportunities from Supabase and sends
a summary to Telegram. Designed to run every Sunday at 10:00 AM UTC.

Run manually:  python weekly_digest.py
Railway cron:  0 10 * * 0
"""

import json
import os
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
DASHBOARD_URL      = os.getenv("DASHBOARD_URL", "").rstrip("/")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

CATEGORY_EMOJI = {
    "PROBLEM":              "🔴",
    "FEATURE_REQUEST":      "🔵",
    "COMPETITOR_COMPLAINT": "🟠",
    "TREND":                "🟢",
    "OTHER":                "⚪",
}

CATEGORY_LABELS = {
    "PROBLEM":              "Problem",
    "FEATURE_REQUEST":      "Feature Request",
    "COMPETITOR_COMPLAINT": "Competitor Complaint",
    "TREND":                "Trend",
    "OTHER":                "Other",
}


def _source_label(source: str) -> str:
    return "HN" if source == "HackerNews" else f"r/{source}"


def _send_telegram(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️  Telegram not configured (missing token or chat_id)")
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
        print(f"⚠️  Telegram error: {e}")
        return False


def fetch_week_opportunities() -> list[dict]:
    """Returns all opportunities created in the last 7 days, ordered by score."""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    result = (
        supabase.table("opportunities")
        .select("id, title, total_score, category, subreddit, url, upvotes, num_comments")
        .gte("created_at", cutoff)
        .eq("is_archived", False)
        .order("total_score", ascending=False)
        .execute()
    )
    return result.data or []


def build_message(opps: list[dict], week_start: datetime, week_end: datetime) -> str:
    total = len(opps)
    top5  = opps[:5]

    # Dominant category
    cat_counts  = Counter(o["category"] for o in opps)
    top_cat     = cat_counts.most_common(1)[0] if cat_counts else ("OTHER", 0)

    # Most active source
    src_counts  = Counter(o["subreddit"] for o in opps)
    top_src     = src_counts.most_common(1)[0] if src_counts else ("—", 0)

    date_range = (
        f"{week_start.strftime('%-d %b')} – {week_end.strftime('%-d %b %Y')}"
        if sys.platform != "win32"
        else f"{week_start.strftime('%d %b')} – {week_end.strftime('%d %b %Y')}"
    )

    # ── Header ────────────────────────────────────────────
    lines = [
        "📊 <b>OpportunityRadar — Weekly Digest</b>",
        f"<i>{date_range}</i>",
        "",
        "📈 <b>Esta semana</b>",
        f"  {total} oportunidades detectadas",
        f"  {CATEGORY_EMOJI.get(top_cat[0], '⚪')} Categoría dominante: "
        f"<b>{CATEGORY_LABELS.get(top_cat[0], top_cat[0])}</b> ({top_cat[1]})",
        f"  🏆 Fuente más activa: <b>{_source_label(top_src[0])}</b> ({top_src[1]} posts)",
        "",
        "━━━━━━━━━━━━━━━━━━━",
        "🎯 <b>Top 5 de la semana</b>",
        "",
    ]

    # ── Top 5 ─────────────────────────────────────────────
    for i, opp in enumerate(top5, 1):
        emoji    = CATEGORY_EMOJI.get(opp["category"], "⚪")
        cat      = CATEGORY_LABELS.get(opp["category"], opp["category"])
        src      = _source_label(opp["subreddit"])
        score    = opp["total_score"]
        title    = opp["title"][:80] + ("…" if len(opp["title"]) > 80 else "")

        lines.append(f"{i}. <b>{score}</b> · {emoji} {cat} · {src}")
        lines.append(f"   <i>{title}</i>")
        lines.append("")

    # ── Footer ────────────────────────────────────────────
    if DASHBOARD_URL:
        lines.append(f'🔗 <a href="{DASHBOARD_URL}">Ver todas las oportunidades</a>')

    return "\n".join(lines)


def main() -> None:
    print(f"📊 Weekly digest — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")

    opps = fetch_week_opportunities()
    if not opps:
        print("  No opportunities found this week — skipping digest.")
        return

    now        = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    message    = build_message(opps, week_start, now)

    print(f"  {len(opps)} opportunities this week, top score: {opps[0]['total_score']}")
    print("  Sending to Telegram...")

    ok = _send_telegram(message)
    if ok:
        print("  ✅ Digest sent successfully.")
    else:
        print("  ❌ Failed to send digest.")
        sys.exit(1)


if __name__ == "__main__":
    main()
