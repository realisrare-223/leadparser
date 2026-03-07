#!/usr/bin/env bash
# =============================================================================
# Phase 2 Verification: Caller Dashboard + Admin Panel + API Routes
# =============================================================================
# Run from repository root:
#   bash tests/phase_checks/check_phase_2.sh
# =============================================================================

set -euo pipefail
PASS=0; FAIL=0
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERCEL="$ROOT/leadparser/vercel-app"

_pass() { echo "  [PASS] $1"; PASS=$((PASS+1)); }
_fail() { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }
_section() { echo; echo "=== $1 ==="; }

# ── Pages ─────────────────────────────────────────────────────────────────────
_section "2.1  App pages"

for PAGE in \
  "app/login/page.tsx" \
  "app/dashboard/page.tsx" \
  "app/admin/page.tsx"; do
  if [[ -f "$VERCEL/$PAGE" ]]; then
    _pass "$PAGE exists"
  else
    _fail "$PAGE NOT FOUND"
  fi
done

# ── API routes ────────────────────────────────────────────────────────────────
_section "2.2  API routes"

for ROUTE in \
  "app/api/leads/route.ts" \
  "app/api/admin/leads/route.ts" \
  "app/api/admin/assign/route.ts" \
  "app/api/admin/stats/route.ts" \
  "app/api/auth/callback/route.ts"; do
  if [[ -f "$VERCEL/$ROUTE" ]]; then
    _pass "$ROUTE exists"
  else
    _fail "$ROUTE NOT FOUND"
  fi
done

# ── Components ────────────────────────────────────────────────────────────────
_section "2.3  Components"

for COMP in \
  "components/LeadTable.tsx" \
  "components/StatusBadge.tsx" \
  "components/StatsGrid.tsx" \
  "components/AssignPanel.tsx"; do
  if [[ -f "$VERCEL/$COMP" ]]; then
    _pass "$COMP exists"
  else
    _fail "$COMP NOT FOUND"
  fi
done

# ── Supabase lib ──────────────────────────────────────────────────────────────
_section "2.4  Supabase lib"

for LIB in \
  "lib/supabase/client.ts" \
  "lib/supabase/server.ts" \
  "lib/types.ts" \
  "middleware.ts"; do
  if [[ -f "$VERCEL/$LIB" ]]; then
    _pass "$LIB exists"
  else
    _fail "$LIB NOT FOUND"
  fi
done

# ── Schema has required tables ────────────────────────────────────────────────
_section "2.5  Supabase schema"

SCHEMA="$ROOT/leadparser/supabase/schema.sql"
if [[ -f "$SCHEMA" ]]; then
  _pass "schema.sql exists"
  for TABLE in leads callers; do
    if grep -qi "CREATE TABLE.*$TABLE" "$SCHEMA"; then
      _pass "schema has $TABLE table"
    else
      _fail "schema missing $TABLE table"
    fi
  done
else
  _fail "schema.sql NOT FOUND"
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo
echo "======================================"
echo "  Phase 2 Results: $PASS passed, $FAIL failed"
echo "======================================"
[[ $FAIL -eq 0 ]] && echo "  Phase 2 COMPLETE" && exit 0
echo "  Phase 2 INCOMPLETE — fix the failures above"; exit 1
