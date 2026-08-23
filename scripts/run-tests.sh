#!/usr/bin/env bash
# Run every standalone offline test script (no pytest) and fail on any failure.
#
#   scripts/run-tests.sh              # uses venv/bin/python
#   scripts/run-tests.sh python3      # override the interpreter (CI)
#
# Excludes tests that need a live server / external services; see EXCLUDED.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${1:-$ROOT/venv/bin/python}"
cd "$ROOT"

# Ensure offline tests have fallback env vars when run in CI (where .env is absent)
export GEMINI_API_KEY="${GEMINI_API_KEY:-test-offline-key-dummy}"
export NORAI_DEV_ACCESS="${NORAI_DEV_ACCESS:-1}"
export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:////tmp/norai_ci_test.db}"

# P1 rate limiting is exercised in test_phase1_hardening.py; every other
# offline suite gets effectively unlimited buckets so multi-step endpoint
# tests never trip the inbound limiter.
export NORAI_RATE_CHAT="${NORAI_RATE_CHAT:-100000}"
export NORAI_RATE_QUIZ="${NORAI_RATE_QUIZ:-100000}"
export NORAI_RATE_PROCESS="${NORAI_RATE_PROCESS:-100000}"
export NORAI_RATE_THREADS="${NORAI_RATE_THREADS:-100000}"

# Tests that need a running backend / paid services — kept out of the offline suite.
EXCLUDED="backend/test_api_contract.py"

failures=0
total=0

mapfile -t tests < <(
  find "$ROOT" -name 'test_*.py' \
    -not -path '*/venv/*' \
    -not -path '*/node_modules/*' \
    -not -path '*/.git/*' \
    -not -path "*/$EXCLUDED" \
    | sort
)

for t in "${tests[@]}"; do
  [ -z "$t" ] && continue
  total=$((total + 1))
  if timeout 300 "$PY" "$t" < /dev/null >/tmp/norai-test.log 2>&1; then
    echo "PASS  $t"
  else
    echo "FAIL  $t"
    echo "------ tail of output ------"
    tail -25 /tmp/norai-test.log
    echo "----------------------------"
    failures=$((failures + 1))
  fi
done


echo ""
echo "$((total - failures))/$total passed, $failures failed"

# ── Pyflakes: catch undefined names before they crash prod ────────────────────
# Specifically guards against BUG-01/02/03 class (missing imports in routers).
echo ""
echo "Running pyflakes on backend/ …"
if "$PY" -m pyflakes backend/ 2>&1 | grep -E "undefined name|unable to detect"; then
  echo "FAIL  pyflakes (undefined names found)"
  failures=$((failures + 1))
else
  echo "PASS  pyflakes backend/"
fi

exit $((failures > 0))
