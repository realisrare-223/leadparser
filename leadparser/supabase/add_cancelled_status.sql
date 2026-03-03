-- ============================================================
-- Migration: Add 'cancelled' status to scraper_jobs
-- Run this ONCE in your Supabase SQL Editor.
-- Allows the frontend to cancel pending/running jobs cleanly.
-- ============================================================

DO $$
BEGIN
  -- Drop old constraint (only has pending/running/done/failed)
  ALTER TABLE scraper_jobs DROP CONSTRAINT IF EXISTS scraper_jobs_status_check;

  -- Re-add with 'cancelled' included
  ALTER TABLE scraper_jobs
    ADD CONSTRAINT scraper_jobs_status_check
    CHECK (status IN ('pending', 'running', 'done', 'failed', 'cancelled'));

EXCEPTION WHEN others THEN
  RAISE NOTICE 'Migration note: %', SQLERRM;
END $$;
