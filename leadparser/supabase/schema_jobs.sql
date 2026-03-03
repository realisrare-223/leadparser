-- ============================================================
-- Scraper Job Queue
-- Run this in your Supabase SQL Editor AFTER schema.sql
-- ============================================================
-- Allows the admin dashboard to queue scrape runs.
-- The worker.py script on your 24/7 PC polls this table,
-- picks up pending jobs, runs main.py, and updates status.
-- ============================================================

CREATE TABLE scraper_jobs (
  id           UUID    DEFAULT gen_random_uuid() PRIMARY KEY,
  city         TEXT    NOT NULL,
  state        TEXT    NOT NULL DEFAULT '',
  niche        TEXT    NOT NULL DEFAULT 'all',
  limit_count  INTEGER NOT NULL DEFAULT 50,
  status       TEXT    NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'running', 'done', 'failed')),
  result_count INTEGER DEFAULT 0,
  error_msg    TEXT    DEFAULT '',
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  started_at   TIMESTAMPTZ,
  finished_at  TIMESTAMPTZ
);

-- RLS: only admins can see/create jobs
ALTER TABLE scraper_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "admin_scraper_jobs" ON scraper_jobs FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM callers c
      WHERE c.id = auth.uid() AND c.role = 'admin'
    )
  );
