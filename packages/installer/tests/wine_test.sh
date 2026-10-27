#!/usr/bin/env bash
set -euo pipefail
EXE="$(readlink -f "$1")"
WORK="$(readlink -m "$2")"
rm -rf "$WORK"
mkdir -p "$WORK"
export WINEPREFIX="$WORK/prefix" WINEDEBUG=-all WINEDLLOVERRIDES="mscoree,mshtml="
unset DISPLAY WAYLAND_DISPLAY

in_x() {
  xvfb-run -a "$@"
}

fail() {
  echo "wine test failed: $*" >&2
  exit 1
}

in_x bash -c 'wineboot -i >/dev/null 2>&1; wineserver -w'
DRIVE="$WINEPREFIX/drive_c"
USERDIR="$(find "$DRIVE/users" -mindepth 1 -maxdepth 1 -type d ! -name Public | head -n 1)"
INSTALL="$USERDIR/AppData/Local/Programs/Keymaster"
SETTINGS="$USERDIR/AppData/Roaming/Keymaster/settings.json"
OFX="$DRIVE/Program Files/Common Files/OFX/Plugins/Keymaster.ofx.bundle"
CEP="$USERDIR/AppData/Roaming/Adobe/CEP/extensions/com.keymaster.adobe"
LINK="$USERDIR/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Keymaster.lnk"

reg_query() {
  in_x wine reg query "$1" 2>/dev/null | tr -d '\r' || true
}

reg_exists() {
  in_x wine reg query "$1" >/dev/null 2>&1
}

in_x bash -c "wine '$EXE' /S /SKIPCORE /COMPONENTS=app,openfx,adobe; wineserver -w"

for path in "$INSTALL/uninstall.exe" "$INSTALL/core/keymaster/cli.py" "$INSTALL/core/install.ps1" "$INSTALL/bin/uv.exe" \
            "$INSTALL/installer/core-step.ps1" "$INSTALL/app/keymaster_app/__main__.py" \
            "$OFX/Contents/Win64/Keymaster.ofx" "$CEP/CSXS/manifest.xml" "$LINK" "$SETTINGS"; do
  [ -e "$path" ] || fail "missing $path"
done
ls "$INSTALL/wheels"/utils3d-*.whl >/dev/null || fail "no utils3d wheel"
grep -q '"core": "C:\\\\users\\\\.*\\\\Keymaster\\\\core"' "$SETTINGS" || fail "settings.json does not point at the core: $(cat "$SETTINGS")"
uninstall_key="$(reg_query 'HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\Keymaster')"
grep -q 'DisplayName    REG_SZ    Keymaster' <<<"$uninstall_key" || fail "no Add/Remove Programs entry"
grep -q 'QuietUninstallString' <<<"$uninstall_key" || fail "no quiet uninstall string"
reg_query 'HKCU\Software\Adobe\CSXS.11' | grep -q 'PlayerDebugMode    REG_SZ    1' || fail "PlayerDebugMode 11 not set"
reg_query 'HKCU\Software\Adobe\CSXS.12' | grep -q 'PlayerDebugMode    REG_SZ    1' || fail "PlayerDebugMode 12 not set"
echo "wine install ok: $(du -sh "$INSTALL" | cut -f1) in $INSTALL"

in_x bash -c "wine '$INSTALL/uninstall.exe' /S; wineserver -w"
for _ in $(seq 1 30); do
  [ -e "$INSTALL" ] || break
  sleep 1
done
for path in "$INSTALL" "$OFX" "$CEP" "$LINK" "$SETTINGS" "$(dirname "$SETTINGS")"; do
  [ ! -e "$path" ] || fail "uninstall left $path"
done
reg_exists 'HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\Keymaster' && fail "uninstall left the Add/Remove Programs entry"
reg_exists 'HKCU\Software\Keymaster' && fail "uninstall left HKCU\\Software\\Keymaster"
reg_query 'HKCU\Software\Adobe\CSXS.11' | grep -q PlayerDebugMode && fail "uninstall left PlayerDebugMode 11"
echo "wine uninstall ok"
