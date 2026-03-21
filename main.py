"""
OpportunityRadar — Main scraping pipeline.

Run directly:  python main.py
Cron trigger:  python cron_job.py
"""

from datetime import datetime, timezone

from scraper import (
    ALERT_MIN_SCORE,
    SUBREDDITS,
    calculate_engagement_score,
    calculate_recurrence_score,
    calculate_urgency_score,
    classify_opportunity,
    is_duplicate,
    notify_opportunity,
    save_opportunity,
    scrape_subreddit,
)
from scraper.database import log_scraping_run, supabase


def process_opportunity(post_data: dict) -> dict | None:
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

    # 3. Recurrence score — MVP defaults to 1 similar thread (score=10)
    #    v2 will implement semantic similarity search
    recurrence_score = calculate_recurrence_score(similar_threads_count=1)

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

    for subreddit in SUBREDDITS:
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
                    result = process_opportunity(post)
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

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    print("─" * 60)
    print(f"✨ Done in {elapsed:.1f}s")
    print(f"   Total processed : {total_processed}")
    print(f"   New opportunities: {total_new}")


if __name__ == "__main__":
    main()
