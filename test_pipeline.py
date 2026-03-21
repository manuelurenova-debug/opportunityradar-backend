"""
OpportunityRadar — Pipeline test (no Reddit API needed)

Simula 8 posts reales de diferentes subreddits y los pasa
por el pipeline completo: scoring → clasificación → Supabase.

Ejecutar:
    python test_pipeline.py
"""

import time
from datetime import datetime, timezone

from scraper.scoring import calculate_engagement_score, calculate_urgency_score
from scraper.scoring import calculate_recurrence_score
from scraper.classifier import classify_opportunity
from scraper.database import is_duplicate, save_opportunity

# ─────────────────────────────────────────────────────────────
# Posts de prueba — simulan casos reales de cada categoría
# ─────────────────────────────────────────────────────────────
MOCK_POSTS = [
    {
        "reddit_id": "test_001",
        "subreddit": "SaaS",
        "title": "I'm desperate for a tool that auto-generates changelogs from Git commits",
        "text": "We spend literally 3 hours every release writing changelogs manually. I've tried everything. Willing to pay $50/month for something that just works. Has anyone found a solution?",
        "url": "https://reddit.com/r/SaaS/test_001",
        "author": "test_user_1",
        "created_utc": int(datetime.now(timezone.utc).timestamp()),
        "upvotes": 342,
        "num_comments": 87,
    },
    {
        "reddit_id": "test_002",
        "subreddit": "startups",
        "title": "Is there any tool that connects Notion with Slack for async standups?",
        "text": "Our remote team is spread across 4 timezones. We need something that pulls Notion tasks and posts a daily digest to Slack automatically. Can't find anything that does both well.",
        "url": "https://reddit.com/r/startups/test_002",
        "author": "test_user_2",
        "created_utc": int(datetime.now(timezone.utc).timestamp()),
        "upvotes": 156,
        "num_comments": 43,
    },
    {
        "reddit_id": "test_003",
        "subreddit": "Entrepreneur",
        "title": "Notion is great but their API is an absolute nightmare for developers",
        "text": "Spent 2 weeks trying to build an integration and the API keeps breaking. Rate limits are ridiculous, documentation is outdated. We're paying $800/month for the team plan and it's still a pain.",
        "url": "https://reddit.com/r/Entrepreneur/test_003",
        "author": "test_user_3",
        "created_utc": int(datetime.now(timezone.utc).timestamp()),
        "upvotes": 891,
        "num_comments": 234,
    },
    {
        "reddit_id": "test_004",
        "subreddit": "nocode",
        "title": "Everyone in my network is asking about AI invoice processing this month",
        "text": "Third conversation this week about automating invoice data extraction. Small businesses are fed up with manual entry. Accountants especially. Something is shifting in this space.",
        "url": "https://reddit.com/r/nocode/test_004",
        "author": "test_user_4",
        "created_utc": int(datetime.now(timezone.utc).timestamp()),
        "upvotes": 67,
        "num_comments": 29,
    },
    {
        "reddit_id": "test_005",
        "subreddit": "indiehackers",
        "title": "I need a dead simple way to collect NPS feedback inside my SaaS",
        "text": "All the existing tools are either too expensive (Delighted is $450/mo) or too complex to set up. I just need a one-question survey after 30 days and store the results. That's it.",
        "url": "https://reddit.com/r/indiehackers/test_005",
        "author": "test_user_5",
        "created_utc": int(datetime.now(timezone.utc).timestamp()),
        "upvotes": 203,
        "num_comments": 61,
    },
    {
        "reddit_id": "test_006",
        "subreddit": "SideProject",
        "title": "Built a weekend project — open to feedback",
        "text": "Finally shipped my side project after 3 months. It's a simple bookmark manager. Nothing revolutionary but I'm proud of it. Would love feedback on the UI.",
        "url": "https://reddit.com/r/SideProject/test_006",
        "author": "test_user_6",
        "created_utc": int(datetime.now(timezone.utc).timestamp()),
        "upvotes": 12,
        "num_comments": 8,
    },
    {
        "reddit_id": "test_007",
        "subreddit": "SaaS",
        "title": "Our customer support team wastes 40% of their time on repetitive tickets — ASAP fix needed",
        "text": "Same 20 questions every single day. We can't find a tool that learns our docs and auto-responds accurately without hallucinating. We've tried Intercom AI, it's garbage for technical products. Frustrated beyond words.",
        "url": "https://reddit.com/r/SaaS/test_007",
        "author": "test_user_7",
        "created_utc": int(datetime.now(timezone.utc).timestamp()),
        "upvotes": 512,
        "num_comments": 143,
    },
    {
        "reddit_id": "test_008",
        "subreddit": "startups",
        "title": "What's everyone using for competitor price monitoring in 2024?",
        "text": "Looking for something that scrapes competitor pricing pages weekly and alerts us when they change. We've been doing this manually and it's a time sink.",
        "url": "https://reddit.com/r/startups/test_008",
        "author": "test_user_8",
        "created_utc": int(datetime.now(timezone.utc).timestamp()),
        "upvotes": 78,
        "num_comments": 34,
    },
]


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def separator(char="─", width=62):
    print(char * width)


def print_result(post, scores, category, saved):
    eng, rec, urg, total = scores
    status = "✅ SAVED" if saved else "⚠️  SKIPPED (duplicate)"
    print(f"\n  reddit_id  : {post['reddit_id']}")
    print(f"  subreddit  : r/{post['subreddit']}")
    print(f"  title      : {post['title'][:60]}...")
    print(f"  category   : {category}")
    print(f"  scores     : engagement={eng:.1f}  recurrence={rec:.1f}  urgency={urg:.1f}")
    print(f"  total      : {total}/100")
    print(f"  status     : {status}")


# ─────────────────────────────────────────────────────────────
# Main test
# ─────────────────────────────────────────────────────────────
def main():
    separator("═")
    print("  OpportunityRadar — Pipeline Test")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    separator("═")

    passed = 0
    failed = 0
    skipped = 0
    results = []

    for i, post in enumerate(MOCK_POSTS, 1):
        print(f"\n[{i}/{len(MOCK_POSTS)}] Testing: {post['title'][:50]}...")

        try:
            # 1. Dedup check
            if is_duplicate(post["reddit_id"]):
                print("  ⚠️  Already in DB — skipping (dedup works correctly)")
                skipped += 1
                continue

            # 2. Scores
            eng = calculate_engagement_score(post["upvotes"], post["num_comments"])
            rec = calculate_recurrence_score(1)
            urg, signals = calculate_urgency_score(f"{post['title']} {post['text']}")
            total = int(eng + rec + urg)

            # 3. Classify
            category = classify_opportunity(post["title"], post["text"])

            # 4. Save
            opportunity = {
                **post,
                "total_score": total,
                "engagement_score": float(eng),
                "recurrence_score": float(rec),
                "urgency_score": float(urg),
                "category": category,
                "evidence": {"urgency_keywords": signals, "top_comments": []},
            }
            saved = save_opportunity(opportunity)

            print_result(post, (eng, rec, urg, total), category, saved)
            results.append({"post": post, "total": total, "category": category})
            passed += 1

            # Small delay to respect Claude rate limits
            time.sleep(0.5)

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            failed += 1

    # ── Summary ──────────────────────────────────────────────
    print(f"\n")
    separator("═")
    print("  RESULTS")
    separator()
    print(f"  ✅ Saved to Supabase : {passed}")
    print(f"  ⚠️  Skipped (dedup)  : {skipped}")
    print(f"  ❌ Errors            : {failed}")

    if results:
        separator()
        print("  SCORE RANKING")
        separator()
        for r in sorted(results, key=lambda x: x["total"], reverse=True):
            bar = "█" * (r["total"] // 5)
            print(f"  {r['total']:3d} {bar:20s} [{r['category'][:20]:20s}] {r['post']['title'][:35]}...")

    separator("═")

    if failed == 0:
        print("\n  🎉 All tests passed — pipeline is working correctly.")
        print("  Check Supabase → Table Editor → opportunities to verify.\n")
    else:
        print(f"\n  ⚠️  {failed} test(s) failed — check errors above.\n")


if __name__ == "__main__":
    main()
