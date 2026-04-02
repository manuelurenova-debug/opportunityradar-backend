import re
import time
import requests
from datetime import datetime, timedelta, timezone

HN_BASE = "https://hacker-news.firebaseio.com/v0"
HEADERS = {"User-Agent": "OpportunityRadar/1.0"}
ITEM_DELAY = 0.1   # seconds between item fetches
MAX_AGE_HOURS = 24

# Hard exclusion — applies to ALL categories
_EXCLUDE_TERMS = [
    # Hardware / semiconductor
    "cpu", "gpu", "chip", "semiconductor", "processor", "risc-v", "fpga",
    "transistor", "circuit board", "motherboard", "dram",
    # Low-level / OS internals
    "kernel", "firmware", "bios", "assembly language", "linker",
    # Vulnerabilities without business context
    "cve-20", "zero-day", "ransomware", "malware",
    # Pure geopolitics
    "ukraine", "gaza", "election result", "congress", "senate",
]

# Inclusion required for general top stories (not Ask/Show HN)
_INCLUDE_TERMS = [
    # Business / entrepreneurship
    "startup", "saas", "founder", "revenue", "customer", "launch", "pricing",
    "business", "entrepreneur", "indie", "bootstrapped", "mrr", "arr",
    # Product / tool
    "tool", "app", "platform", "api", "service", "product", "software",
    "automation", "workflow", "productivity",
    # AI in business context
    "llm", "agent", "openai", "claude", "gpt", "copilot",
    # Active signals
    "how to", "how do", "what is the best", "looking for", "freelance",
]

# Minimum HN score per list type
_MIN_SCORE = {
    "ask":  10,
    "show": 10,
    "top":  50,
}


def _strip_html(html: str) -> str:
    """Removes HTML tags and decodes basic entities."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#x27;", "'").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def _is_excluded(title: str) -> bool:
    t = title.lower()
    return any(term in t for term in _EXCLUDE_TERMS)


def _has_inclusion(title: str) -> bool:
    t = title.lower()
    return any(term in t for term in _INCLUDE_TERMS)


def _fetch_ids(endpoint: str, limit: int) -> list[int]:
    resp = requests.get(f"{HN_BASE}/{endpoint}.json", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()[:limit]


def _fetch_item(item_id: int) -> dict | None:
    resp = requests.get(f"{HN_BASE}/item/{item_id}.json", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _item_to_post(item: dict, list_type: str) -> dict | None:
    """
    Converts a raw HN item to the standard post dict.
    Returns None if the item should be skipped.
    """
    # Only process stories (not comments, jobs, polls)
    if item.get("type") != "story":
        return None

    title = item.get("title", "").strip()
    if not title:
        return None

    score = item.get("score", 0)
    created_utc = item.get("time", 0)

    # Age filter
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    if datetime.fromtimestamp(created_utc, tz=timezone.utc) < cutoff:
        return None

    # Score threshold
    if score < _MIN_SCORE[list_type]:
        return None

    # Exclusion filter (all lists)
    if _is_excluded(title):
        return None

    # Inclusion filter (top stories only)
    if list_type == "top" and not _has_inclusion(title):
        return None

    item_id = item.get("id")
    url = item.get("url") or f"https://news.ycombinator.com/item?id={item_id}"
    raw_text = item.get("text", "") or ""
    text = _strip_html(raw_text)

    return {
        "reddit_id": f"hn_{item_id}",
        "subreddit": "HackerNews",
        "title": title,
        "text": text,
        "url": url,
        "author": item.get("by", "[deleted]"),
        "created_utc": created_utc,
        "upvotes": score,
        "num_comments": item.get("descendants", 0),
    }


def scrape_hn(
    ask_limit: int = 50,
    show_limit: int = 50,
    top_limit: int = 100,
) -> list[dict]:
    """
    Fetches and filters posts from Hacker News.
    Returns a deduplicated list of post dicts ready for the pipeline.
    """
    # Collect IDs per list type (deduplicate across lists)
    id_queue: list[tuple[int, str]] = []  # (id, list_type)
    seen_ids: set[int] = set()

    for endpoint, list_type, limit in [
        ("askstories",  "ask",  ask_limit),
        ("showstories", "show", show_limit),
        ("topstories",  "top",  top_limit),
    ]:
        try:
            ids = _fetch_ids(endpoint, limit)
            for item_id in ids:
                if item_id not in seen_ids:
                    seen_ids.add(item_id)
                    id_queue.append((item_id, list_type))
        except requests.RequestException as e:
            print(f"  ⚠️  Could not fetch {endpoint}: {e}")

    # Fetch and filter items
    posts: list[dict] = []
    for item_id, list_type in id_queue:
        try:
            item = _fetch_item(item_id)
            if item:
                post = _item_to_post(item, list_type)
                if post:
                    posts.append(post)
        except requests.RequestException:
            pass  # skip failed item fetches silently
        time.sleep(ITEM_DELAY)

    return posts
