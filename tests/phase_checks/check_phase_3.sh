#!/usr/bin/env bash
# =============================================================================
# Phase 3 Verification: Scraper Job Queue + Worker + Admin Trigger
# =============================================================================
# Run from repository root:
#   bash tests/phase_checks/check_phase_3.sh
# =============================================================================

set -euo pipefail
PASS=0; FAIL=0
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERCEL="$ROOT/leadparser/vercel-app"
LP="$ROOT/leadparser"

_pass() { echo "  [PASS] $1"; PASS=$((PASS+1)); }
_fail() { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }
_section() { echo; echo "=== $1 ==="; }

# ── Python worker ─────────────────────────────────────────────────────────────
_section "3.1  Python worker"

if [[ -f "$LP/worker.py" ]]; then
  _pass "worker.py exists"
else
  _fail "worker.py NOT FOUND"
fi

if [[ -f "$LP/scheduler.py" ]]; then
  _pass "scheduler.py exists"
else
  _fail "scheduler.py NOT FOUND"
fi

# ── Scraper jobs schema ───────────────────────────────────────────────────────
_section "3.2  Scraper jobs schema"

JOBS_SCHEMA="$LP/supabase/schema_jobs.sql"
if [[ -f "$JOBS_SCHEMA" ]]; then
  _pass "schema_jobs.sql exists"
  if grep -qi "scraper_jobs" "$JOBS_SCHEMA"; then
    _pass "schema_jobs.sql has scraper_jobs table"
  else
    _fail "schema_jobs.sql missing scraper_jobs table"
  fi
else
  _fail "schema_jobs.sql NOT FOUND"
fi

# ── API route for job creation ────────────────────────────────────────────────
_section "3.3  Scraper job API route"

SCRAPE_ROUTE="$VERCEL/app/api/admin/scrape"
if [[ -d "$SCRAPE_ROUTE" ]]; then
  _pass "api/admin/scrape route directory exists"
  if [[ -f "$SCRAPE_ROUTE/route.ts" ]]; then
    _pass "api/admin/scrape/route.ts exists"
  else
    _fail "api/admin/scrape/route.ts NOT FOUND"
  fi
else
  _fail "api/admin/scrape directory NOT FOUND"
fi

# ── Job status in types.ts ────────────────────────────────────────────────────
_section "3.4  TypeScript types for jobs"

TYPES="$VERCEL/lib/types.ts"
if grep -q "ScraperJob" "$TYPES" 2>/dev/null; then
  _pass "types.ts contains ScraperJob interface"
else
  _fail "types.ts missing ScraperJob interface"
fi

if grep -q "JobStatus" "$TYPES" 2>/dev/null; then
  _pass "types.ts contains JobStatus type"
else
  _fail "types.ts missing JobStatus type"
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo
echo "======================================"
echo "  Phase 3 Results: $PASS passed, $FAIL failed"
echo "======================================"
[[ $FAIL -eq 0 ]] && echo "  Phase 3 COMPLETE" && exit 0
echo "  Phase 3 INCOMPLETE — fix the failures above"; exit 1
