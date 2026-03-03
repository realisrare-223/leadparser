-- ============================================================
-- LeadParser Central Database Schema
-- Run this in your Supabase SQL Editor (supabase.com/dashboard)
-- ============================================================

-- Lead lifecycle status
CREATE TYPE lead_status AS ENUM ('new', 'called', 'sold', 'followup', 'dead');

-- ============================================================
-- CALLERS TABLE
-- Extends auth.users with name + role
-- Run AFTER creating users in Supabase Auth dashboard
-- ============================================================
CREATE TABLE callers (
  id         UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
  name       TEXT NOT NULL,
  role       TEXT DEFAULT 'caller' CHECK (role IN ('caller', 'admin')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- LEADS TABLE
-- Central lead storage with CRM fields
-- ============================================================
CREATE TABLE leads (
  -- Identity
  id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  dedup_key    TEXT UNIQUE NOT NULL,   -- MD5(lower(name)|lower(city))

  -- Core business info
  niche            TEXT    NOT NULL,
  name             TEXT    NOT NULL,
  phone            TEXT    DEFAULT '',
  secondary_phone  TEXT    DEFAULT '',
  address          TEXT    DEFAULT '',
  city             TEXT    DEFAULT '',
  state            TEXT    DEFAULT '',
  zip_code         TEXT    DEFAULT '',
  hours            TEXT    DEFAULT '',
  review_count     INTEGER DEFAULT 0,
  rating           TEXT    DEFAULT '',
  gmb_link         TEXT    DEFAULT '',
  website          TEXT    DEFAULT '',
  facebook         TEXT    DEFAULT '',
  instagram        TEXT    DEFAULT '',
  data_source      TEXT    DEFAULT 'Google Maps',

  -- Scoring & pitch
  lead_score       INTEGER DEFAULT 0,
  pitch_notes      TEXT    DEFAULT '',
  additional_notes TEXT    DEFAULT '',

  -- CRM / assignment fields
  status           lead_status   DEFAULT 'new',
  assigned_to      UUID REFERENCES callers(id),
  assigned_at      TIMESTAMPTZ,
  call_status      TEXT    DEFAULT '',
  follow_up_date   DATE,
  caller_notes     TEXT    DEFAULT '',

  -- Timestamps
  date_added       DATE    DEFAULT CURRENT_DATE,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- ============================================================

-- Unique phone dedup (only applies to non-empty phones)
CREATE UNIQUE INDEX idx_leads_phone
  ON leads (phone) WHERE phone != '' AND phone != 'NOT FOUND';

-- Query performance
CREATE INDEX idx_leads_niche       ON leads (niche);
CREATE INDEX idx_leads_city        ON leads (city);
CREATE INDEX idx_leads_status      ON leads (status);
CREATE INDEX idx_leads_assigned_to ON leads (assigned_to);
CREATE INDEX idx_leads_score       ON leads (lead_score DESC);
CREATE INDEX idx_leads_date        ON leads (created_at DESC);

-- ============================================================
-- AUTO-UPDATE updated_at TRIGGER
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER leads_updated_at
  BEFORE UPDATE ON leads
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================
ALTER TABLE leads   ENABLE ROW LEVEL SECURITY;
ALTER TABLE callers ENABLE ROW LEVEL SECURITY;

-- Callers: see + update their own profile
CREATE POLICY "callers_own_profile"
  ON callers FOR ALL
  USING (id = auth.uid());

-- Admins: see all caller profiles
CREATE POLICY "admin_all_callers"
  ON callers FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM callers c
      WHERE c.id = auth.uid() AND c.role = 'admin'
    )
  );

-- Callers: can only SELECT their assigned leads
CREATE POLICY "caller_select_own_leads"
  ON leads FOR SELECT
  USING (assigned_to = auth.uid());

-- Callers: can UPDATE status/notes on their own leads
CREATE POLICY "caller_update_own_leads"
  ON leads FOR UPDATE
  USING (assigned_to = auth.uid())
  WITH CHECK (assigned_to = auth.uid());

-- Admins: full access to all leads
CREATE POLICY "admin_all_leads"
  ON leads FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM callers c
      WHERE c.id = auth.uid() AND c.role = 'admin'
    )
  );

-- ============================================================
-- SERVICE ROLE (Python scraper uses service role key)
-- Service role bypasses RLS automatically — no policy needed.
-- ============================================================

-- ============================================================
-- HELPER VIEWS
-- ============================================================

-- Quick stats view for admin dashboard
CREATE VIEW lead_stats AS
SELECT
  COUNT(*)                                           AS total,
  COUNT(*) FILTER (WHERE status = 'new')             AS new_count,
  COUNT(*) FILTER (WHERE assigned_to IS NOT NULL)    AS assigned,
  COUNT(*) FILTER (WHERE status = 'called')          AS called,
  COUNT(*) FILTER (WHERE status = 'sold')            AS sold,
  COUNT(*) FILTER (WHERE status = 'followup')        AS followup,
  COUNT(*) FILTER (WHERE status = 'dead')            AS dead,
  COUNT(*) FILTER (WHERE lead_score >= 18)           AS hot,
  COUNT(*) FILTER (WHERE lead_score >= 12 AND lead_score < 18) AS warm,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE status = 'sold') /
    NULLIF(COUNT(*) FILTER (WHERE status IN ('called', 'sold', 'dead')), 0),
    1
  )                                                  AS conversion_pct
FROM leads;

-- Per-caller stats view
CREATE VIEW caller_stats AS
SELECT
  c.id,
  c.name,
  c.role,
  COUNT(l.id)                                        AS total_assigned,
  COUNT(l.id) FILTER (WHERE l.status = 'called')    AS called,
  COUNT(l.id) FILTER (WHERE l.status = 'sold')      AS sold,
  COUNT(l.id) FILTER (WHERE l.status = 'followup')  AS followup,
  COUNT(l.id) FILTER (WHERE l.status = 'new')       AS untouched,
  ROUND(
    100.0 * COUNT(l.id) FILTER (WHERE l.status = 'sold') /
    NULLIF(COUNT(l.id) FILTER (WHERE l.status IN ('called', 'sold', 'dead')), 0),
    1
  )                                                  AS conversion_pct
FROM callers c
LEFT JOIN leads l ON l.assigned_to = c.id
GROUP BY c.id, c.name, c.role;
