#!/usr/bin/env bash
set -euo pipefail
status=0
for t in packages/*/test.sh; do
  [ -f "$t" ] || continue
  echo "::group::$t"
  bash "$t" || status=1
  echo "::endgroup::"
done
exit $status
