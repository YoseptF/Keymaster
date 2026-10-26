#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
PY=${PYTHON:-python3}

"$PY" -m unittest discover -s "$HERE/tests" -t "$HERE" -p 'test_*.py'

if ! command -v blender >/dev/null 2>&1; then
  echo "blender not on PATH, skipping the headless Blender tests"
  exit 0
fi

TMP="$ROOT/tmp/blender-test"
rm -rf "$TMP"
mkdir -p "$TMP/dist"
"$PY" "$HERE/build.py" --out "$TMP/dist" --version 0.0.0-test.1 >/dev/null
ZIP="$TMP/dist/keymaster-blender-0.0.0-test.1.zip"
blender --background --factory-startup --command extension validate "$ZIP"

run_blender() {
  local mode=$1
  local work="$TMP/$mode"
  mkdir -p "$work/user"
  env -u KEYMASTER_LANGUAGE -u KEYMASTER_FAKE_FAIL -u KEYMASTER_FAKE_DELAY \
    BLENDER_USER_RESOURCES="$work/user" \
    KEYMASTER_SETTINGS="$work/settings.json" \
    KEYMASTER_CORE="$ROOT/packages/core/testing/fake_core" \
    KEYMASTER_PYTHON="$PY" \
    blender --background --factory-startup --python-exit-code 1 \
      --python "$HERE/tests/blender_test.py" -- --mode "$mode" --source "$HERE/keymaster" --zip "$ZIP" --tmp "$work"
}

run_blender source
run_blender zip
echo "blender tests ok"
