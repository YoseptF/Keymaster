#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"
cd "$HERE"
export PYTHONDONTWRITEBYTECODE=1
"$PY" -m unittest discover -s tests -t . -p 'test_*.py' -v
if "$PY" -c "import PySide6.QtWidgets" >/dev/null 2>&1; then
  echo "PySide6 found: the offscreen window test ran above"
else
  echo "PySide6 not installed for $PY: the offscreen window test was skipped"
fi
