-- ============================================================
-- Migration: Add scraper_logs table
-- Run this ONCE in your Supabase SQL Editor.
-- Enables live log streaming from worker.py to the dashboard.
-- ============================================================

CREATE TABLE IF NOT EXISTS scraper_logs (
  id      BIGSERIAL    PRIMARY KEY,
  job_id  UUID         REFERENCES scraper_jobs(id) ON DELETE CASCADE,
  ts      TIMESTAMPTZ  DEFAULT now(),
  level   TEXT         DEFAULT 'info',   -- 'debug' | 'info' | 'warning' | 'error'
  message TEXT         NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scraper_logs_job_id ON scraper_logs (job_id, id);

ALTER TABLE scraper_logs ENABLE ROW LEVEL SECURITY;

-- Any authenticated user (admin) can read logs
CREATE POLICY "auth_read_scraper_logs"
  ON scraper_logs FOR SELECT
  USING (auth.uid() IS NOT NULL);

-- Service role (Python worker) writes — no policy needed (service role bypasses RLS)
