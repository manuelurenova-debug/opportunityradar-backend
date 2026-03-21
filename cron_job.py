"""
OpportunityRadar — Cron job entry point.

This file is designed to be called by a scheduler (Railway, Render, GitHub Actions).
It runs main() and exits with code 0 on success or 1 on failure.

Railway cron schedule:  0 * * * *   (every hour)
GitHub Actions example: see .github/workflows/scrape.yml
"""

import sys
import traceback

from main import main

if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
