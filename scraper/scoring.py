import json
import math
import os
import re

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

URGENCY_KEYWORDS = [
    # Intención de pago directa
    "willing to pay", "budget for", "paying for", "pay for", "would pay",
    # Búsqueda activa de solución
    "looking for", "need a solution", "any recommendations", "can anyone suggest",
    "what tool", "what do you use", "how do you handle", "alternative to",
    "switched from", "replacing",
    # Pain + frustración
    "frustrated with", "struggling with", "fed up", "hate using", "tired of",
    "desperate", "nightmare", "painful", "waste time", "hours lost",
    # Urgencia temporal
    "ASAP", "urgent", "immediately",
    # Señales originales que funcionaban
    "cannot find", "literally", "need",
]

# Stop words para keyword matching de recurrence
_STOP_WORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "any", "can",
    "had", "her", "was", "one", "our", "out", "day", "get", "has", "him",
    "his", "how", "its", "may", "new", "now", "old", "see", "two", "way",
    "who", "boy", "did", "its", "let", "put", "say", "she", "too", "use",
    "that", "this", "with", "have", "from", "they", "will", "been", "does",
    "were", "what", "your", "when", "more", "also", "into", "over", "just",
    "like", "make", "some", "time", "than", "then", "them", "well", "even",
    "want", "look", "only", "come", "back", "know", "good", "need", "very",
    "most", "much", "such", "long", "down", "year", "work", "here", "take",
    "each", "many", "made", "give", "same", "help", "used", "last", "next",
    "feel", "real", "keep", "high", "open", "seem", "hard", "find", "send",
    "ask", "end", "try", "run", "own", "set", "move", "live", "turn",
    "show", "say", "play", "both", "tell", "hold", "side", "part", "read",
    "around", "going", "doing", "using", "being", "having", "think", "about",
    "there", "their", "which", "could", "other", "after", "would", "these",
    "those", "start", "still", "thing", "great", "right", "first", "never",
    "every", "might", "small", "large", "place", "where", "while", "again",
    "since", "under", "build", "built", "really", "always", "little", "often",
}


def extract_keywords(text: str) -> set[str]:
    """Extracts meaningful keywords (words ≥ 4 chars, no stop words)."""
    words = re.findall(r'\b[a-z]{4,}\b', text.lower())
    return {w for w in words if w not in _STOP_WORDS}


def count_similar_posts(title: str, recent_titles: list[str]) -> int:
    """
    Counts how many recent posts share ≥ 2 keywords with this title.
    Used to calculate recurrence score.
    """
    keywords = extract_keywords(title)
    if len(keywords) < 2:
        return 0

    count = 0
    for recent_title in recent_titles:
        shared = keywords & extract_keywords(recent_title)
        if len(shared) >= 2:
            count += 1

    return count


def calculate_engagement_score(upvotes: int, num_comments: int) -> float:
    """
    Log-scale engagement score. Max: 40 points (20 upvotes + 20 comments).
    Saturates at 1000 upvotes / 500 comments so high-engagement posts
    score meaningfully higher than mid-range ones.
    """
    if upvotes == 0:
        upvote_score = 0.0
    else:
        upvote_score = min(20.0, (math.log10(upvotes + 1) / math.log10(1001)) * 20)

    if num_comments == 0:
        comment_score = 0.0
    else:
        comment_score = min(20.0, (math.log10(num_comments + 1) / math.log10(501)) * 20)

    return upvote_score + comment_score


def calculate_recurrence_score(similar_threads_count: int) -> float:
    """
    Scores how frequently this problem appears across threads.
    Max: 30 points.
    """
    if similar_threads_count == 0:
        return 5.0
    elif similar_threads_count <= 2:
        return 10.0
    elif similar_threads_count <= 5:
        return 20.0
    else:
        return 30.0


def calculate_urgency_score(text: str) -> tuple[float, list[str]]:
    """
    Uses Claude Haiku to detect urgency and willingness-to-pay signals.
    Returns (score, signals_found) where score is 0, 10, 20, or 30.

    Scoring tiers:
      30 — high confidence + 2 or more signals
      20 — high confidence OR 2+ signals
      10 — low confidence but urgency detected
       0 — no urgency
    """
    has_question = "?" in text

    prompt = f"""Analyze this Reddit post for urgency and willingness to pay signals.

Post: {text[:1000]}

{"Note: The title contains a question mark, which often indicates active solution-seeking." if has_question else ""}

Keywords to look for: {URGENCY_KEYWORDS}

Return ONLY a JSON object with this exact format:
{{
  "has_urgency": true,
  "confidence": 0.85,
  "signals_found": ["willing to pay", "frustrated with"]
}}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )

        result_text = response.content[0].text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result = json.loads(result_text)

        signals = result.get("signals_found", [])
        confidence = float(result.get("confidence", 0))

        if not result.get("has_urgency", False):
            return 0.0, signals

        signals_count = len(signals)
        if confidence > 0.7 and signals_count >= 2:
            return 30.0, signals
        elif confidence > 0.7 or signals_count >= 2:
            return 20.0, signals
        elif confidence > 0.4:
            return 10.0, signals
        else:
            return 0.0, signals

    except Exception as e:
        print(f"    ⚠️  Urgency scoring error: {e}")
        return 0.0, []
