#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pkg="$(cd "$here/../.." && pwd)"
repo="$(cd "$pkg/../.." && pwd)"
natron="${NATRON_DIR:?set NATRON_DIR to an unpacked portable Natron}"
work="${KM_NATRON_WORK:-$repo/tmp/natron-run}"
bundle_dir="${KM_BUNDLE_DIR:-$pkg/build/test}"

rm -rf "$work"
mkdir -p "$work/home" "$work/out"
python3 "$here/make_clip.py" "$work/clip" 5

run() {
  env -i PATH="/usr/bin:/bin" DISPLAY="" HOME="$work/home" LANG="${KM_NATRON_LANG:-en_US.UTF-8}" \
    OFX_PLUGIN_PATH="$bundle_dir" XDG_CACHE_HOME="$work/home/.cache" XDG_CONFIG_HOME="$work/home/.config" \
    KEYMASTER_PYTHON="$(command -v python3)" KEYMASTER_CORE="$repo/packages/core/testing/fake_core" \
    KM_NATRON_CLIP="$work/clip/frame_####.png" "$@" \
    "$natron/NatronRenderer" --no-settings -t "$here/key_clip.py" < /dev/null
}

check() {
  local file="$1" want="$2"
  local got
  got="$(python3 "$here/read_png.py" "$file" 64 36)"
  echo "$file: $got"
  case "$got" in
    *"$want"*) ;;
    *) echo "expected '$want' in $file" >&2; exit 1 ;;
  esac
}

echo "== key and render the cutout"
run KM_NATRON_OUT="$work/out/cut_####.png" KM_NATRON_OUTPUT=0 KM_NATRON_PROJECT="$work/keyed.ntp" 2>&1 | tee "$work/run1.log" | grep -E "^KM_|rror|Keymaster" || true
grep -q "KM_RESULT rendered" "$work/run1.log"
for f in 1 3 5; do check "$work/out/cut_000$f.png" "alpha=[0.784] red=[0.784]"; done

echo "== reopen the saved project without keying again and render the alpha"
run KM_NATRON_OUT="$work/out/alpha_####.png" KM_NATRON_LOAD="$work/keyed.ntp" KM_NATRON_PRESS=0 KM_NATRON_OUTPUT=1 2>&1 | tee "$work/run2.log" | grep -E "^KM_|rror" || true
grep -q "KM_RESULT rendered" "$work/run2.log"
grep -q "KM_TOKEN [0-9a-f]" "$work/run2.log"
for f in 1 4; do check "$work/out/alpha_000$f.png" "alpha=[1.0] red=[0.898]"; done

echo "== no key pressed passes the source through"
KM_NATRON_LANG=es_MX.UTF-8 run KM_NATRON_OUT="$work/out/pass_####.png" KM_NATRON_PRESS=0 2>&1 | tee "$work/run3.log" | grep -E "^KM_|rror" || true
grep -q "KM_LABEL Procesar clip" "$work/run3.log"
check "$work/out/pass_0002.png" "alpha=[1.0] red=[0.118, 0.706]"
echo "natron end-to-end ok"
