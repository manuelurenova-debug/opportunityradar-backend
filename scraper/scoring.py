import json
import math
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

URGENCY_KEYWORDS = [
    "desperate", "ASAP", "willing to pay", "need", "frustrated",
    "literally", "cannot find", "waste time", "fed up", "pay for",
    "nightmare", "hours lost", "painful",
]


def calculate_engagement_score(upvotes: int, num_comments: int) -> float:
    """
    Log-scale engagement score to prevent viral posts from dominating.
    Max: 40 points (20 upvotes + 20 comments).
    """
    # Upvotes component (max 20)
    if upvotes == 0:
        upvote_score = 0.0
    else:
        upvote_score = min(20.0, (math.log10(upvotes + 1) / math.log10(101)) * 20)

    # Comments component (max 20)
    if num_comments == 0:
        comment_score = 0.0
    else:
        comment_score = min(20.0, (math.log10(num_comments + 1) / math.log10(51)) * 20)

    return upvote_score + comment_score


def calculate_recurrence_score(similar_threads_count: int) -> float:
    """
    Scores how frequently this problem appears across threads.
    Max: 30 points.
    """
    if similar_threads_count == 1:
        return 10.0
    elif similar_threads_count <= 3:
        return 20.0
    else:
        return 30.0


def calculate_urgency_score(text: str) -> tuple[float, list[str]]:
    """
    Uses Claude Haiku to detect urgency and willingness-to-pay signals.
    Returns (score, signals_found) where score is 0, 15, or 30.
    """
    prompt = f"""Analyze this Reddit post for urgency and willingness to pay.

Post: {text[:1000]}

Keywords to look for: {URGENCY_KEYWORDS}

Return ONLY a JSON object with this exact format:
{{
  "has_urgency": true,
  "confidence": 0.85,
  "signals_found": ["willing to pay", "frustrated"]
}}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )

        result_text = response.content[0].text.strip()
        # Strip markdown code fences if present
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result = json.loads(result_text)

        signals = result.get("signals_found", [])
        confidence = float(result.get("confidence", 0))

        if result.get("has_urgency", False):
            if confidence > 0.7:
                return 30.0, signals
            elif confidence > 0.4:
                return 15.0, signals

        return 0.0, signals

    except Exception as e:
        print(f"    ⚠️  Urgency scoring error: {e}")
        return 0.0, []
