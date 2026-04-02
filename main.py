"""
OpportunityRadar — Main scraping pipeline.

Run directly:  python main.py
Cron trigger:  python cron_job.py
"""

import time
from datetime import datetime, timezone

from scraper import (
    ALERT_MIN_SCORE,
    SUBREDDITS,
    calculate_engagement_score,
    calculate_recurrence_score,
    calculate_urgency_score,
    count_similar_posts,
    classify_opportunity,
    fetch_recent_titles,
    is_duplicate,
    notify_opportunity,
    save_opportunity,
    scrape_subreddit,
    scrape_hn,
)
from scraper.database import log_scraping_run, supabase


def process_opportunity(post_data: dict, recent_titles: list[str]) -> dict | None:
    """
    Full pipeline for a single post:
      1. Dedup check
      2. Score (engagement + recurrence + urgency)
      3. Classify category
      4. Save to Supabase
    """
    # 1. Skip duplicates
    if is_duplicate(post_data["reddit_id"]):
        return None

    # 2. Engagement score (no API call)
    engagement_score = calculate_engagement_score(
        post_data["upvotes"],
        post_data["num_comments"],
    )

    # 3. Recurrence score — keyword overlap with last 7 days of posts
    similar_count = count_similar_posts(post_data["title"], recent_titles)
    recurrence_score = calculate_recurrence_score(similar_count)

    # 4. Urgency score via Claude Haiku
    full_text = f"{post_data['title']} {post_data['text']}"
    urgency_score, urgency_signals = calculate_urgency_score(full_text)

    total_score = int(engagement_score + recurrence_score + urgency_score)

    # 5. Category classification via Claude Haiku
    category = classify_opportunity(post_data["title"], post_data["text"])

    # 6. Build evidence object
    evidence = {
        "urgency_keywords": urgency_signals,
        "top_comments": [],  # TODO v2: fetch top comments
    }

    # 7. Assemble and save
    opportunity = {
        **post_data,
        "total_score": total_score,
        "engagement_score": float(engagement_score),
        "recurrence_score": float(recurrence_score),
        "urgency_score": float(urgency_score),
        "category": category,
        "evidence": evidence,
    }

    saved = save_opportunity(opportunity)

    # Telegram alert if score meets threshold
    if saved and saved.get("total_score", 0) >= ALERT_MIN_SCORE:
        notified = notify_opportunity(saved)
        if notified:
            supabase.table("opportunities").update({
                "notified": True,
                "notified_at": datetime.now(timezone.utc).isoformat(),
                "notification_channel": "telegram",
            }).eq("id", saved["id"]).execute()

    return saved


def main() -> None:
    """Main scraping loop — iterates all configured subreddits."""
    started = datetime.now(timezone.utc)
    print(f"🚀 OpportunityRadar starting at {started.strftime('%Y-%m-%d %H:%M:%S')} UTC\n")

    total_processed = 0
    total_new = 0

    # Fetch recent titles once — used for recurrence scoring across all posts
    print("📂 Loading recent posts for recurrence scoring...")
    try:
        recent_titles = fetch_recent_titles(days=7)
        print(f"   {len(recent_titles)} posts from last 7 days loaded\n")
    except Exception as e:
        print(f"   ⚠️  Could not load recent titles: {e} — recurrence will default to 0\n")
        recent_titles = []

    for i, subreddit in enumerate(SUBREDDITS):
        if i > 0:
            time.sleep(1.0)  # 1 request/sec — Reddit public API rate limit

        sub_start = datetime.now(timezone.utc)
        print(f"📡 Scraping r/{subreddit}...")

        posts_scraped = 0
        posts_new = 0
        posts_skipped = 0
        errors: list[str] = []

        try:
            posts = scrape_subreddit(subreddit, limit=100)
            posts_scraped = len(posts)
            print(f"   Found {posts_scraped} qualifying posts")

            for post in posts:
                try:
                    result = process_opportunity(post, recent_titles)
                    if result:
                        posts_new += 1
                        total_new += 1
                        print(
                            f"   ✅ [{result['category']:22s}] "
                            f"Score {result['total_score']:3d} | "
                            f"{post['title'][:60]}..."
                        )
                    else:
                        posts_skipped += 1

                    total_processed += 1

                except Exception as e:
                    err = f"Error on post {post.get('reddit_id', '?')}: {e}"
                    errors.append(err)
                    print(f"   ❌ {err}")

        except Exception as e:
            err = f"Subreddit scrape failed: {e}"
            errors.append(err)
            print(f"   ❌ {err}")

        # Log this subreddit run
        try:
            log_scraping_run(
                subreddit=subreddit,
                posts_scraped=posts_scraped,
                posts_new=posts_new,
                posts_skipped=posts_skipped,
                errors=errors,
                started_at=sub_start,
            )
        except Exception as e:
            print(f"   ⚠️  Could not write scraping log: {e}")

        print(f"   → {posts_new} new, {posts_skipped} skipped\n")

    # ── Hacker News ──────────────────────────────────────────
    time.sleep(1.0)
    hn_start = datetime.now(timezone.utc)
    print("📡 Scraping Hacker News (Ask HN / Show HN / Top)...")

    hn_scraped = 0
    hn_new = 0
    hn_skipped = 0
    hn_errors: list[str] = []

    try:
        hn_posts = scrape_hn()
        hn_scraped = len(hn_posts)
        print(f"   Found {hn_scraped} qualifying posts")

        for post in hn_posts:
            try:
                result = process_opportunity(post, recent_titles)
                if result:
                    hn_new += 1
                    total_new += 1
                    print(
                        f"   ✅ [{result['category']:22s}] "
                        f"Score {result['total_score']:3d} | "
                        f"{post['title'][:60]}..."
                    )
                else:
                    hn_skipped += 1

                total_processed += 1

            except Exception as e:
                err = f"Error on HN post {post.get('reddit_id', '?')}: {e}"
                hn_errors.append(err)
                print(f"   ❌ {err}")

    except Exception as e:
        err = f"HN scrape failed: {e}"
        hn_errors.append(err)
        print(f"   ❌ {err}")

    try:
        log_scraping_run(
            subreddit="HackerNews",
            posts_scraped=hn_scraped,
            posts_new=hn_new,
            posts_skipped=hn_skipped,
            errors=hn_errors,
            started_at=hn_start,
        )
    except Exception as e:
        print(f"   ⚠️  Could not write HN scraping log: {e}")

    print(f"   → {hn_new} new, {hn_skipped} skipped\n")

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    print("─" * 60)
    print(f"✨ Done in {elapsed:.1f}s")
    print(f"   Total processed : {total_processed}")
    print(f"   New opportunities: {total_new}")


if __name__ == "__main__":
    main()
