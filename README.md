# OpportunityRadar — Backend

Scans Reddit for validated business opportunities using Claude AI scoring.

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your Reddit, Anthropic, and Supabase credentials

# 3. Create Supabase tables
# Run schema.sql in your Supabase SQL Editor

# 4. Run the scraper
python main.py
```

## Architecture

```
main.py              ← orchestrates the full pipeline
cron_job.py          ← entry point for scheduled runs (exit 0/1)
scraper/
  reddit_scraper.py  ← PRAW: fetch hot posts from 5 subreddits
  scoring.py         ← engagement score (math) + urgency score (Claude)
  classifier.py      ← category classification (Claude)
  database.py        ← Supabase read/write
```

## Scoring formula

| Component       | Max | Method             |
|-----------------|-----|--------------------|
| Engagement      |  40 | log10(upvotes + comments) |
| Recurrence      |  30 | similar thread count |
| Urgency         |  30 | Claude Haiku NLP   |
| **Total**       | **100** |              |

## Deployment (Railway)

1. Push repo to GitHub
2. Connect repo in Railway
3. Set environment variables
4. Add cron schedule: `0 * * * *`
5. Set start command: `python cron_job.py`
