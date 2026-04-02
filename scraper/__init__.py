from .reddit_scraper import scrape_subreddit, SUBREDDITS
from .hn_scraper import scrape_hn
from .scoring import (
    calculate_engagement_score,
    calculate_recurrence_score,
    calculate_urgency_score,
    count_similar_posts,
)
from .classifier import classify_opportunity
from .database import save_opportunity, is_duplicate, fetch_recent_titles
from .notifier import notify_opportunity, should_notify, ALERT_MIN_SCORE

__all__ = [
    "scrape_subreddit",
    "scrape_hn",
    "SUBREDDITS",
    "calculate_engagement_score",
    "calculate_recurrence_score",
    "calculate_urgency_score",
    "count_similar_posts",
    "classify_opportunity",
    "save_opportunity",
    "is_duplicate",
    "fetch_recent_titles",
    "notify_opportunity",
    "should_notify",
    "ALERT_MIN_SCORE",
]
