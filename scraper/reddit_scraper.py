import time
import requests
from datetime import datetime, timedelta, timezone

SUBREDDITS = ["SaaS", "startups", "Entrepreneur", "nocode", "indiehackers", "SideProject"]

HEADERS = {
    "User-Agent": "OpportunityRadar/1.0",
}

REQUEST_DELAY = 1.0  # seconds between requests (Reddit rate limit)


def scrape_subreddit(subreddit_name: str, limit: int = 100) -> list[dict]:
    """
    Scrapes recent posts from a subreddit using Reddit's public JSON endpoint.

    Args:
        subreddit_name: Name of the subreddit (without r/)
        limit: Maximum number of posts to fetch (max 100 per request)

    Returns:
        List of post dicts with reddit metadata
    """
    url = f"https://www.reddit.com/r/{subreddit_name}/new.json"
    params = {"limit": min(limit, 100)}

    response = requests.get(url, headers=HEADERS, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()
    children = data.get("data", {}).get("children", [])

    posts = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    for child in children:
        post = child.get("data", {})

        created_utc = post.get("created_utc", 0)
        post_time = datetime.fromtimestamp(created_utc, tz=timezone.utc)

        # Skip posts older than 24 hours
        if post_time < cutoff:
            continue

        # Skip pinned/stickied posts
        if post.get("stickied"):
            continue

        upvotes = post.get("score", 0)
        num_comments = post.get("num_comments", 0)

        # Skip low-engagement noise
        if upvotes < 5 and num_comments < 2:
            continue

        is_self = post.get("is_self", False)
        permalink = post.get("permalink", "")

        posts.append({
            "reddit_id": post.get("id"),
            "subreddit": subreddit_name,
            "title": post.get("title", ""),
            "text": post.get("selftext", "") if is_self else "",
            "url": f"https://reddit.com{permalink}" if is_self else post.get("url", ""),
            "author": post.get("author", "[deleted]"),
            "created_utc": int(created_utc),
            "upvotes": upvotes,
            "num_comments": num_comments,
        })

    return posts


def scrape_all_subreddits(limit: int = 100) -> list[dict]:
    """
    Scrapes all configured subreddits with rate limiting.

    Returns:
        Combined list of posts from all subreddits
    """
    all_posts = []

    for i, subreddit in enumerate(SUBREDDITS):
        if i > 0:
            time.sleep(REQUEST_DELAY)

        try:
            posts = scrape_subreddit(subreddit, limit=limit)
            print(f"  r/{subreddit}: {len(posts)} posts")
            all_posts.extend(posts)
        except requests.RequestException as e:
            print(f"  r/{subreddit}: ERROR — {e}")

    return all_posts
