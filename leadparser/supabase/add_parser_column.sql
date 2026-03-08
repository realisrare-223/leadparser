-- Migration: add parser column to scraper_jobs
-- Run this in the Supabase SQL Editor.
-- Adds which scraper engine was used for each job: playwright | xhr | selenium

ALTER TABLE scraper_jobs
  ADD COLUMN IF NOT EXISTS parser TEXT NOT NULL DEFAULT 'playwright'
    CHECK (parser IN ('playwright', 'xhr', 'selenium'));

-- Also ensure date_added is present in leads (already in schema, this is a safety guard)
-- ALTER TABLE leads ADD COLUMN IF NOT EXISTS date_added DATE;
