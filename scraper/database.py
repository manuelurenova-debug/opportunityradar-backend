import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY"),
)


def is_duplicate(reddit_id: str) -> bool:
    """Returns True if this reddit_id already exists in the database."""
    result = (
        supabase.table("opportunities")
        .select("id")
        .eq("reddit_id", reddit_id)
        .execute()
    )
    return len(result.data) > 0


def save_opportunity(opportunity: dict) -> dict | None:
    """
    Inserts a new opportunity into Supabase.

    Returns the saved row dict, or None on failure.
    """
    # Serialize evidence JSONB field
    if isinstance(opportunity.get("evidence"), dict):
        opportunity["evidence"] = json.dumps(opportunity["evidence"])

    result = supabase.table("opportunities").insert(opportunity).execute()
    return result.data[0] if result.data else None


def log_scraping_run(
    subreddit: str,
    posts_scraped: int,
    posts_new: int,
    posts_skipped: int,
    errors: list[str],
    started_at: datetime,
) -> None:
    """Records a scraping run to the scraping_logs table."""
    supabase.table("scraping_logs").insert({
        "subreddit": subreddit,
        "posts_scraped": posts_scraped,
        "posts_new": posts_new,
        "posts_skipped": posts_skipped,
        "errors": errors,
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
