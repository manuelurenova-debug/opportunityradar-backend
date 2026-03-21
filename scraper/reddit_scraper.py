import os
import praw
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Reddit API client
reddit = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent="OpportunityRadar/1.0",
)

SUBREDDITS = ["SaaS", "startups", "Entrepreneur", "nocode", "indiehackers", "SideProject"]


def scrape_subreddit(subreddit_name: str, limit: int = 100, time_filter: str = "day") -> list[dict]:
    """
    Scrapes recent posts from a subreddit.

    Args:
        subreddit_name: Name of the subreddit (without r/)
        limit: Maximum number of posts to fetch
        time_filter: 'hour', 'day', or 'week'

    Returns:
        List of post dicts with reddit metadata
    """
    subreddit = reddit.subreddit(subreddit_name)
    posts = []

    for post in subreddit.hot(limit=limit):
        # Skip posts older than 24 hours
        post_age = datetime.utcnow() - datetime.utcfromtimestamp(post.created_utc)
        if post_age > timedelta(hours=24):
            continue

        # Skip pinned/stickied posts
        if post.stickied:
            continue

        # Skip low-engagement noise
        if post.score < 5 and post.num_comments < 2:
            continue

        posts.append({
            "reddit_id": post.id,
            "subreddit": subreddit_name,
            "title": post.title,
            "text": post.selftext if post.is_self else "",
            "url": post.url if not post.is_self else f"https://reddit.com{post.permalink}",
            "author": str(post.author) if post.author else "[deleted]",
            "created_utc": int(post.created_utc),
            "upvotes": post.score,
            "num_comments": post.num_comments,
        })

    return posts
