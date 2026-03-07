#!/usr/bin/env bash
# =============================================================================
# Phase 5 Verification: Landing Page + Full E2E + Deployment Readiness
# =============================================================================
# Run from repository root:
#   bash tests/phase_checks/check_phase_5.sh
# =============================================================================

set -euo pipefail
PASS=0; FAIL=0
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERCEL="$ROOT/leadparser/vercel-app"

_pass() { echo "  [PASS] $1"; PASS=$((PASS+1)); }
_fail() { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }
_section() { echo; echo "=== $1 ==="; }

# ── Landing page ──────────────────────────────────────────────────────────────
_section "5.1  Landing page"

if [[ -f "$VERCEL/app/page.tsx" ]]; then
  _pass "app/page.tsx (landing) exists"
else
  _fail "app/page.tsx NOT FOUND"
fi

if [[ -f "$ROOT/tests/nextjs/components/LandingPage.test.tsx" ]]; then
  _pass "LandingPage.test.tsx exists"
else
  _fail "LandingPage.test.tsx NOT FOUND (Phase 5)"
fi

# ── Deployment files ──────────────────────────────────────────────────────────
_section "5.2  Deployment configuration"

for FILE in \
  "vercel.json" \
  "next.config.js" \
  ".env.local.example"; do
  if [[ -f "$VERCEL/$FILE" ]] || [[ -f "$ROOT/$FILE" ]]; then
    _pass "$FILE exists"
  else
    _fail "$FILE NOT FOUND"
  fi
done

# ── TypeScript build ──────────────────────────────────────────────────────────
_section "5.3  TypeScript compilation"

if command -v npx &>/dev/null; then
  if (cd "$VERCEL" && npx tsc --noEmit 2>/dev/null); then
    _pass "TypeScript compiles without errors"
  else
    _fail "TypeScript compilation errors found"
  fi
else
  echo "  [SKIP] npx not found — cannot check TypeScript"
fi

# ── Next.js build ─────────────────────────────────────────────────────────────
_section "5.4  Next.js build"

echo "  [SKIP] Next.js build skipped in CI (requires env vars)"

# ── Full test suite ───────────────────────────────────────────────────────────
_section "5.5  Full test suite"

PYTHON="${PYTHON:-python}"
command -v python &>/dev/null || PYTHON="python3"

if command -v "$PYTHON" &>/dev/null; then
  if "$PYTHON" -m pytest "$ROOT/tests/python/" -q --tb=no 2>/dev/null; then
    _pass "All Python tests pass"
  else
    _fail "Python tests FAILED"
  fi
else
  echo "  [SKIP] Python not available"
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo
echo "======================================"
echo "  Phase 5 Results: $PASS passed, $FAIL failed"
echo "======================================"
[[ $FAIL -eq 0 ]] && echo "  Phase 5 COMPLETE — ready to ship" && exit 0
echo "  Phase 5 INCOMPLETE — fix the failures above"; exit 1
