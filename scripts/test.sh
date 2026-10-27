#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
status=0
echo "::group::scripts/tests"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -t scripts -p 'test_*.py' || status=1
echo "::endgroup::"
for t in packages/*/test.sh; do
  [ -f "$t" ] || continue
  echo "::group::$t"
  bash "$t" || status=1
  echo "::endgroup::"
done
exit $status
