#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHON="${PYTHON:-python3}"
node --check "$HERE/extension/js/panel.js"
for f in "$HERE"/extension/js/lib/*.js; do node --check "$f"; done
node --test --test-reporter=spec "$HERE"/tests/*.test.js
