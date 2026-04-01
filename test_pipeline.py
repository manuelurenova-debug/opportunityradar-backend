"""
OpportunityRadar — Pipeline test with real Reddit data

Fetches live posts from all configured subreddits and runs them
through the full pipeline: scoring → classification → Supabase.

Ejecutar:
    python test_pipeline.py
"""

import time
from datetime import datetime, timezone

from scraper.reddit_scraper import scrape_subreddit, SUBREDDITS, REQUEST_DELAY
from scraper.scoring import calculate_engagement_score, calculate_urgency_score
from scraper.scoring import calculate_recurrence_score
from scraper.classifier import classify_opportunity
from scraper.database import is_duplicate, save_opportunity


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
    print("  OpportunityRadar — Pipeline Test (Live Reddit Data)")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    separator("═")

    # Fetch real posts from Reddit
    print("\n📡 Fetching posts from Reddit...\n")
    all_posts = []
    for i, subreddit in enumerate(SUBREDDITS):
        if i > 0:
            time.sleep(REQUEST_DELAY)
        try:
            posts = scrape_subreddit(subreddit, limit=10)
            print(f"  r/{subreddit}: {len(posts)} posts fetched")
            all_posts.extend(posts)
        except Exception as e:
            print(f"  r/{subreddit}: ERROR — {e}")

    if not all_posts:
        print("\n❌ No posts fetched — check your internet connection.")
        return

    print(f"\n  Total posts to process: {len(all_posts)}")
    separator()

    passed = 0
    failed = 0
    skipped = 0
    results = []

    for i, post in enumerate(all_posts, 1):
        print(f"\n[{i}/{len(all_posts)}] {post['title'][:55]}...")

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

            time.sleep(0.5)  # respect Claude rate limits

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
