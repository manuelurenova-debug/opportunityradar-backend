-- OpportunityRadar — Supabase schema
-- Run this in your Supabase project's SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────
-- Opportunities table
-- ─────────────────────────────────────────
CREATE TABLE opportunities (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Reddit metadata
  reddit_id     TEXT UNIQUE NOT NULL,
  subreddit     TEXT NOT NULL,
  title         TEXT NOT NULL,
  text          TEXT,
  url           TEXT,
  author        TEXT,
  created_utc   BIGINT NOT NULL,

  -- Engagement metrics
  upvotes       INTEGER DEFAULT 0,
  num_comments  INTEGER DEFAULT 0,

  -- AI Scoring (0-100)
  total_score       INTEGER,
  engagement_score  DECIMAL(5,2),
  recurrence_score  DECIMAL(5,2),
  urgency_score     DECIMAL(5,2),

  -- Classification
  category  TEXT CHECK (category IN ('PROBLEM', 'FEATURE_REQUEST', 'COMPETITOR_COMPLAINT', 'TREND', 'OTHER')),

  -- Evidence
  evidence  JSONB,  -- {urgency_keywords: [], top_comments: []}

  -- Metadata
  processed_at  TIMESTAMPTZ DEFAULT NOW(),
  created_at    TIMESTAMPTZ DEFAULT NOW(),

  -- Alerts (Telegram / future channels)
  notified        BOOLEAN DEFAULT FALSE,
  notified_at     TIMESTAMPTZ,
  notification_channel  TEXT,           -- 'telegram', 'email', etc.

  -- Exports
  exported        BOOLEAN DEFAULT FALSE,
  exported_at     TIMESTAMPTZ,
  export_format   TEXT,                 -- 'csv', 'notion', 'airtable', etc.

  -- Soft delete / archiving
  is_archived     BOOLEAN DEFAULT FALSE,

  CONSTRAINT valid_score CHECK (total_score >= 0 AND total_score <= 100)
);

CREATE INDEX idx_opportunities_score     ON opportunities(total_score DESC);
CREATE INDEX idx_opportunities_subreddit ON opportunities(subreddit);
CREATE INDEX idx_opportunities_created   ON opportunities(created_at DESC);
CREATE INDEX idx_opportunities_category  ON opportunities(category);

-- ─────────────────────────────────────────
-- Scraping log table
-- ─────────────────────────────────────────
CREATE TABLE scraping_logs (
  id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  subreddit      TEXT NOT NULL,
  posts_scraped  INTEGER DEFAULT 0,
  posts_new      INTEGER DEFAULT 0,
  posts_skipped  INTEGER DEFAULT 0,
  errors         TEXT[],
  started_at     TIMESTAMPTZ DEFAULT NOW(),
  completed_at   TIMESTAMPTZ
);

-- ─────────────────────────────────────────
-- Thread similarity (v2 — recurrence scoring)
-- ─────────────────────────────────────────
CREATE TABLE thread_similarity (
  id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  opportunity_id   UUID REFERENCES opportunities(id),
  similar_thread_id TEXT,
  similarity_score  DECIMAL(3,2),
  detected_at       TIMESTAMPTZ DEFAULT NOW()
);
