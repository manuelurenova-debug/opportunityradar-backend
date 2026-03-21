import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

VALID_CATEGORIES = {"PROBLEM", "FEATURE_REQUEST", "COMPETITOR_COMPLAINT", "TREND", "OTHER"}


def classify_opportunity(title: str, text: str) -> str:
    """
    Uses Claude Haiku to classify a Reddit post into a business opportunity category.

    Returns one of: PROBLEM, FEATURE_REQUEST, COMPETITOR_COMPLAINT, TREND, OTHER
    """
    prompt = f"""Classify this Reddit post into ONE category:

Categories:
- PROBLEM: User describes a pain point or problem they experience
- FEATURE_REQUEST: User asks "is there a tool for X?" or "I wish X existed" or "I need X"
- COMPETITOR_COMPLAINT: User complains about an existing tool or solution
- TREND: Multiple people discussing the same emerging topic
- OTHER: Does not fit any of the above

Title: {title}
Text: {text[:500]}

Return ONLY the category name (e.g., PROBLEM). No explanation."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}],
        )

        category = response.content[0].text.strip().upper()

        # Validate against known categories
        if category in VALID_CATEGORIES:
            return category

        # Try to extract if Claude added extra text
        for valid in VALID_CATEGORIES:
            if valid in category:
                return valid

        return "OTHER"

    except Exception as e:
        print(f"    ⚠️  Classification error: {e}")
        return "OTHER"
