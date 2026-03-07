#!/usr/bin/env bash
# =============================================================================
# Phase 4 Verification: Email Extractor + Captcha Detection + Multi-query Maps
# =============================================================================
# Run from repository root:
#   bash tests/phase_checks/check_phase_4.sh
# =============================================================================

set -euo pipefail
PASS=0; FAIL=0
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LP="$ROOT/leadparser"

_pass() { echo "  [PASS] $1"; PASS=$((PASS+1)); }
_fail() { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }
_section() { echo; echo "=== $1 ==="; }

# ── Email extractor ───────────────────────────────────────────────────────────
_section "4.1  Email extractor"

if [[ -f "$LP/utils/email_extractor.py" ]]; then
  _pass "email_extractor.py exists"
else
  _fail "email_extractor.py NOT FOUND"
fi

if [[ -f "$ROOT/tests/python/unit/test_email_extractor.py" ]]; then
  _pass "test_email_extractor.py exists"
else
  _fail "test_email_extractor.py NOT FOUND"
fi

# ── Captcha detector ─────────────────────────────────────────────────────────
_section "4.2  Captcha detector"

if [[ -f "$LP/utils/captcha_detector.py" ]]; then
  _pass "captcha_detector.py exists"
else
  _fail "captcha_detector.py NOT FOUND"
fi

if [[ -f "$ROOT/tests/python/unit/test_captcha_detector.py" ]]; then
  _pass "test_captcha_detector.py exists"
else
  _fail "test_captcha_detector.py NOT FOUND"
fi

# ── Multi-query Google Maps integration test ──────────────────────────────────
_section "4.3  Multi-query integration test"

if [[ -f "$ROOT/tests/python/integration/test_google_maps_multiquery.py" ]]; then
  _pass "test_google_maps_multiquery.py exists"
else
  _fail "test_google_maps_multiquery.py NOT FOUND"
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo
echo "======================================"
echo "  Phase 4 Results: $PASS passed, $FAIL failed"
echo "======================================"
[[ $FAIL -eq 0 ]] && echo "  Phase 4 COMPLETE" && exit 0
echo "  Phase 4 INCOMPLETE — fix the failures above"; exit 1
