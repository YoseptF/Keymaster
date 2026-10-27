#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PY="${PYTHON:-python3}"
cd "$HERE"
export PYTHONDONTWRITEBYTECODE=1
"$PY" -m unittest discover -s tests -t . -p 'test_*.py' "$@"
if command -v makensis >/dev/null 2>&1 && command -v wine >/dev/null 2>&1 && command -v xvfb-run >/dev/null 2>&1; then
  WORK="$ROOT/tmp/installer-wine-test"
  rm -rf "$WORK"
  mkdir -p "$WORK"
  "$PY" - "$WORK" <<'PYEOF'
import sys
from pathlib import Path
sys.path.insert(0, ".")
from tests import helpers
work = Path(sys.argv[1])
downloads = helpers.fake_downloads(work / "downloads")
prebuilt = helpers.prebuilt_dir(work / "prebuilt")
helpers.build(work / "dist", "windows", prebuilt, helpers.test_pins(work, downloads), work / "cache")
PYEOF
  bash "$HERE/tests/wine_test.sh" "$WORK/dist/keymaster-installer-0.0.0-test.1-windows.exe" "$WORK/wine"
else
  echo "makensis, wine or xvfb-run missing: the silent Wine install test was skipped"
fi
