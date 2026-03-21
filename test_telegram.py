"""
Test rápido del notifier de Telegram.
Envía una alerta de prueba con un post simulado.

Ejecutar:
    python test_telegram.py
"""

from scraper.notifier import notify_opportunity, ALERT_MIN_SCORE, _send_telegram

# Post de prueba con score alto para que supere el umbral
MOCK_OPPORTUNITY = {
    "id": "test-uuid-telegram-001",
    "reddit_id": "test_telegram_001",
    "subreddit": "SaaS",
    "title": "I'm desperate for a tool that auto-generates changelogs from Git commits",
    "category": "PROBLEM",
    "total_score": 78,
    "engagement_score": 18.4,
    "recurrence_score": 10.0,
    "urgency_score": 30.0,
    "upvotes": 342,
    "num_comments": 87,
    "url": "https://reddit.com/r/SaaS/comments/test001",
    "notified": False,
    "evidence": {
        "urgency_keywords": ["desperate", "willing to pay"],
        "top_comments": [],
    },
}

if __name__ == "__main__":
    print(f"📨 Sending test Telegram alert (min score configured: {ALERT_MIN_SCORE})...\n")

    success = notify_opportunity(MOCK_OPPORTUNITY)

    if success:
        print("✅ Alert sent! Check your Telegram.")
    else:
        print("❌ Alert failed. Check your TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
