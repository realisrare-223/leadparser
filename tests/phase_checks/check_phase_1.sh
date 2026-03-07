#!/usr/bin/env bash
# =============================================================================
# Phase 1 Verification: DB Migration + TypeScript Types + Python Tests
# =============================================================================
# Run from repository root:
#   bash tests/phase_checks/check_phase_1.sh
# =============================================================================

set -euo pipefail
PASS=0; FAIL=0
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

_pass() { echo "  [PASS] $1"; PASS=$((PASS+1)); }
_fail() { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }
_section() { echo; echo "=== $1 ==="; }

# ── 1.1  Migration file exists ────────────────────────────────────────────────
_section "1.1  DB Migration SQL"

MIGRATION="$ROOT/leadparser/supabase/migrations/001_add_crm_columns.sql"
if [[ -f "$MIGRATION" ]]; then
  _pass "001_add_crm_columns.sql exists"
else
  _fail "001_add_crm_columns.sql NOT FOUND at $MIGRATION"
fi

if grep -q "call_attempts" "$MIGRATION" 2>/dev/null; then
  _pass "Migration contains call_attempts column"
else
  _fail "Migration missing call_attempts column"
fi

if grep -q "last_called_at" "$MIGRATION" 2>/dev/null; then
  _pass "Migration contains last_called_at column"
else
  _fail "Migration missing last_called_at column"
fi

if grep -q "email" "$MIGRATION" 2>/dev/null; then
  _pass "Migration contains email column"
else
  _fail "Migration missing email column"
fi

# ── 1.2  TypeScript types updated ────────────────────────────────────────────
_section "1.2  lib/types.ts"

TYPES="$ROOT/leadparser/vercel-app/lib/types.ts"
if [[ -f "$TYPES" ]]; then
  _pass "lib/types.ts exists"
else
  _fail "lib/types.ts NOT FOUND"
fi

for FIELD in email call_attempts last_called_at; do
  if grep -q "$FIELD" "$TYPES" 2>/dev/null; then
    _pass "types.ts contains $FIELD"
  else
    _fail "types.ts missing $FIELD"
  fi
done

# ── 1.3  supabase_handler LEAD_COLUMNS ───────────────────────────────────────
_section "1.3  supabase_handler.py LEAD_COLUMNS"

HANDLER="$ROOT/leadparser/exporters/supabase_handler.py"
if [[ -f "$HANDLER" ]]; then
  _pass "supabase_handler.py exists"
else
  _fail "supabase_handler.py NOT FOUND"
fi

if grep -q '"email"' "$HANDLER" 2>/dev/null; then
  _pass "supabase_handler LEAD_COLUMNS contains email"
else
  _fail "supabase_handler LEAD_COLUMNS missing email"
fi

# ── 1.4-1.5  Test directory structure ────────────────────────────────────────
_section "1.4-1.5  Test directory structure"

for DIR in \
  "$ROOT/tests/python/unit" \
  "$ROOT/tests/python/integration" \
  "$ROOT/tests/nextjs/components" \
  "$ROOT/tests/nextjs/api" \
  "$ROOT/tests/phase_checks"; do
  if [[ -d "$DIR" ]]; then
    _pass "Directory exists: ${DIR#$ROOT/}"
  else
    _fail "Directory MISSING: ${DIR#$ROOT/}"
  fi
done

# ── 1.6-1.10  Python unit test files exist ───────────────────────────────────
_section "1.6-1.10  Python unit test files"

for FILE in \
  test_lead_scorer \
  test_phone_validator \
  test_address_parser \
  test_pitch_engine \
  test_sentiment_analyzer; do
  if [[ -f "$ROOT/tests/python/unit/${FILE}.py" ]]; then
    _pass "${FILE}.py exists"
  else
    _fail "${FILE}.py NOT FOUND"
  fi
done

# ── 1.11  Integration test file ──────────────────────────────────────────────
_section "1.11  Integration test file"

if [[ -f "$ROOT/tests/python/integration/test_supabase_handler.py" ]]; then
  _pass "test_supabase_handler.py exists"
else
  _fail "test_supabase_handler.py NOT FOUND"
fi

# ── 1.12-1.14  Next.js test infrastructure ───────────────────────────────────
_section "1.12-1.14  Next.js test infrastructure"

if [[ -f "$ROOT/leadparser/vercel-app/vitest.config.ts" ]]; then
  _pass "vitest.config.ts exists"
else
  _fail "vitest.config.ts NOT FOUND"
fi

if [[ -f "$ROOT/tests/nextjs/setup.ts" ]]; then
  _pass "tests/nextjs/setup.ts exists"
else
  _fail "tests/nextjs/setup.ts NOT FOUND"
fi

if [[ -f "$ROOT/tests/nextjs/components/LeadTable.test.tsx" ]]; then
  _pass "LeadTable.test.tsx exists"
else
  _fail "LeadTable.test.tsx NOT FOUND"
fi

if grep -q '"test"' "$ROOT/leadparser/vercel-app/package.json" 2>/dev/null; then
  _pass "package.json has test script"
else
  _fail "package.json missing test script"
fi

if grep -q '"vitest"' "$ROOT/leadparser/vercel-app/package.json" 2>/dev/null; then
  _pass "package.json includes vitest dependency"
else
  _fail "package.json missing vitest dependency"
fi

# ── 1.16  Python tests run (requires pytest installed) ───────────────────────
_section "1.16  Python tests run"

if command -v python &>/dev/null || command -v python3 &>/dev/null; then
  PYTHON="${PYTHON:-python}"
  command -v python &>/dev/null || PYTHON="python3"

  if "$PYTHON" -m pytest "$ROOT/tests/python/" -q --tb=no 2>/dev/null; then
    _pass "Python tests pass"
  else
    _fail "Python tests FAILED (run: python -m pytest tests/python/ -v for details)"
  fi
else
  echo "  [SKIP] Python not found — cannot run tests"
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo
echo "======================================"
echo "  Phase 1 Results: $PASS passed, $FAIL failed"
echo "======================================"

if [[ $FAIL -eq 0 ]]; then
  echo "  Phase 1 COMPLETE"
  exit 0
else
  echo "  Phase 1 INCOMPLETE — fix the failures above"
  exit 1
fi
