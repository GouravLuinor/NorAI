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

# Tests that need a running backend / paid services — kept out of the offline suite.
EXCLUDED="backend/test_api_contract.py"

failures=0
total=0
while IFS= read -r t; do
  total=$((total + 1))
  if timeout 300 "$PY" "$t" >/tmp/norai-test.log 2>&1; then
    echo "PASS  $t"
  else
    echo "FAIL  $t"
    echo "------ tail of output ------"
    tail -25 /tmp/norai-test.log
    echo "----------------------------"
    failures=$((failures + 1))
  fi
done < <(
  find "$ROOT" -name 'test_*.py' \
    -not -path '*/venv/*' \
    -not -path '*/node_modules/*' \
    -not -path '*/.git/*' \
    -not -path "*/$EXCLUDED" \
    | sort
)

echo ""
echo "$((total - failures))/$total passed, $failures failed"
exit $((failures > 0))
