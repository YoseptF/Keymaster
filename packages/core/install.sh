#!/usr/bin/env bash
set -euo pipefail

CORE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$CORE/.venv"
PY="$VENV/bin/python"
TORCH_INDEX="https://download.pytorch.org/whl/cu128"

say() { printf '%s\n' "$*" >&2; }

supported() {
  "$1" -c 'import sys; sys.exit(0 if sys.version_info[:2] in ((3, 12), (3, 13)) else 1)' 2>/dev/null
}

if [ -x "$PY" ] && ! supported "$PY"; then
  say "Removing $VENV: it does not use Python 3.12 or 3.13"
  rm -rf "$VENV"
fi

if [ ! -x "$PY" ]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv --python 3.12 "$VENV"
  else
    base=""
    for candidate in python3.12 python3.13 python3; do
      if command -v "$candidate" >/dev/null 2>&1 && supported "$candidate"; then
        base="$candidate"
        break
      fi
    done
    if [ -z "$base" ]; then
      say "Keymaster needs Python 3.12 or 3.13 (or uv, which can fetch it). Install one and run this again."
      exit 1
    fi
    "$base" -m venv "$VENV"
  fi
fi

if command -v uv >/dev/null 2>&1; then
  pip_install() { uv pip install --python "$PY" "$@"; }
else
  "$PY" -m pip install --upgrade pip >/dev/null
  pip_install() { "$PY" -m pip install "$@"; }
fi

REQUIREMENTS="$CORE/upstream/requirements.txt"
if [ -n "${KEYMASTER_WHEELS:-}" ] && [ -d "$KEYMASTER_WHEELS" ]; then
  LOCAL_REQUIREMENTS="$(mktemp)"
  trap 'rm -f "$LOCAL_REQUIREMENTS"' EXIT
  while IFS= read -r line || [ -n "$line" ]; do
    name="${line%% @ git+*}"
    if [ "$name" != "$line" ]; then
      wheel="$(find "$KEYMASTER_WHEELS" -maxdepth 1 -name "${name//-/_}-*.whl" | sort | tail -n 1)"
      [ -n "$wheel" ] && line="$name @ file://$(cd "$(dirname "$wheel")" && pwd)/$(basename "$wheel")"
    fi
    printf '%s\n' "$line"
  done < "$REQUIREMENTS" > "$LOCAL_REQUIREMENTS"
  REQUIREMENTS="$LOCAL_REQUIREMENTS"
fi

pip_install torch==2.9.1 torchvision==0.24.1 --index-url "$TORCH_INDEX"
pip_install -r "$REQUIREMENTS"

cd "$CORE"
"$PY" -m keymaster setup
"$PY" -m keymaster doctor || true
