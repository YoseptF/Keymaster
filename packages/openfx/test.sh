#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
build="${KEYMASTER_OPENFX_BUILD:-$here/build/test}"

missing=()
command -v cmake >/dev/null || missing+=(cmake)
command -v g++ >/dev/null || missing+=(g++)
command -v nm >/dev/null || missing+=(binutils)
if [ ${#missing[@]} -gt 0 ]; then
  if [ "$(id -u)" -eq 0 ] && command -v apt-get >/dev/null; then
    apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${missing[@]}" >/dev/null
  else
    echo "openfx tests need: ${missing[*]}" >&2
    exit 1
  fi
fi

cmake -S "$here" -B "$build" -DCMAKE_BUILD_TYPE=Release -DKEYMASTER_TESTS=ON >/dev/null
cmake --build "$build" -j "$(nproc)"
exports="$(nm -D --defined-only "$build/Keymaster.ofx" | awk '$2 == "T" {print $3}' | sort | tr '\n' ' ')"
if [ "$exports" != "OfxGetNumberOfPlugins OfxGetPlugin " ]; then
  echo "Keymaster.ofx exports unexpected symbols: $exports" >&2
  exit 1
fi
ctest --test-dir "$build" --output-on-failure
