#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/tmp/app-dev"
mkdir -p "$WORK"
cd "$ROOT/packages/app"
if [ "${1:-}" = "--real" ]; then
  shift
  exec python3 -m keymaster_app "$@"
fi
export KEYMASTER_SETTINGS="${KEYMASTER_SETTINGS:-$WORK/settings.json}"
export KEYMASTER_CORE="$ROOT/packages/core/testing/fake_core"
export KEYMASTER_PYTHON="${KEYMASTER_PYTHON:-python3}"
export KEYMASTER_FAKE_DELAY="${KEYMASTER_FAKE_DELAY:-0.05}"
exec "$KEYMASTER_PYTHON" -m keymaster_app "$@"
