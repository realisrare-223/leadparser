-- ============================================================
-- RLS Fix + Worker Status Table
-- Run this in Supabase SQL Editor (one time)
-- ============================================================
-- Problem: admin_all_callers policy queries the callers table
-- inside a policy ON the callers table = infinite recursion.
-- Fix: use a SECURITY DEFINER function that bypasses RLS.
-- ============================================================

-- Step 1: Create a bypass helper function
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN LANGUAGE sql SECURITY DEFINER STABLE AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.callers
    WHERE id = auth.uid() AND role = 'admin'
  );
$$;

-- Step 2: Drop the broken recursive policies
DROP POLICY IF EXISTS "admin_all_callers" ON callers;
DROP POLICY IF EXISTS "admin_all_leads"   ON leads;

-- Step 3: Recreate them using the safe helper
CREATE POLICY "admin_all_callers"
  ON callers FOR ALL
  USING (public.is_admin());

CREATE POLICY "admin_all_leads"
  ON leads FOR ALL
  USING (public.is_admin());

-- ============================================================
-- Worker Status Table (heartbeat for live "engine online" indicator)
-- ============================================================
CREATE TABLE IF NOT EXISTS worker_status (
  id        INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- singleton row
  last_seen TIMESTAMPTZ
);

INSERT INTO worker_status (id, last_seen) VALUES (1, NULL)
  ON CONFLICT DO NOTHING;

ALTER TABLE worker_status ENABLE ROW LEVEL SECURITY;

-- Any logged-in user can read worker status
CREATE POLICY "auth_read_worker_status"
  ON worker_status FOR SELECT
  USING (auth.uid() IS NOT NULL);
