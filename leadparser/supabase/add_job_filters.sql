-- ============================================================
-- Migration: Add progress tracking + filter columns to scraper_jobs
-- Run this ONCE in your Supabase SQL Editor.
-- Enables per-job progress bars and per-job filter overrides.
-- ============================================================

ALTER TABLE scraper_jobs
  ADD COLUMN IF NOT EXISTS progress        INTEGER  DEFAULT 0,       -- 0-100 percent
  ADD COLUMN IF NOT EXISTS min_reviews     INTEGER  DEFAULT 0,
  ADD COLUMN IF NOT EXISTS max_reviews     INTEGER  DEFAULT 9999,
  ADD COLUMN IF NOT EXISTS min_rating      NUMERIC  DEFAULT 0.0,
  ADD COLUMN IF NOT EXISTS max_rating      NUMERIC  DEFAULT 5.0,
  -- 'any' = no filter | 'yes' = has website | 'no' = no website
  ADD COLUMN IF NOT EXISTS website_filter  TEXT     DEFAULT 'any',
  ADD COLUMN IF NOT EXISTS require_phone   BOOLEAN  DEFAULT true,    -- always true in the UI
  ADD COLUMN IF NOT EXISTS min_score       INTEGER  DEFAULT 0;

-- Add the check constraint separately so IF NOT EXISTS still works on the column
DO $$
BEGIN
  ALTER TABLE scraper_jobs
    ADD CONSTRAINT scraper_jobs_website_filter_check
    CHECK (website_filter IN ('any', 'yes', 'no'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
