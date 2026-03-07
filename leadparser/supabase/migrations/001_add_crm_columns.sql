-- Migration 001: Add CRM tracking columns to leads table
-- Run this in the Supabase SQL Editor ONCE before Phase 2 features are used.

ALTER TABLE leads
  ADD COLUMN IF NOT EXISTS email          TEXT        DEFAULT '',
  ADD COLUMN IF NOT EXISTS call_attempts  INTEGER     DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_called_at TIMESTAMPTZ;

-- Index for follow-up scheduling queries (show leads due today)
CREATE INDEX IF NOT EXISTS idx_leads_follow_up
  ON leads (follow_up_date) WHERE follow_up_date IS NOT NULL;

-- Index for email lookup (analytics + dedup)
CREATE INDEX IF NOT EXISTS idx_leads_email
  ON leads (email) WHERE email != '';
