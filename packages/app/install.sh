#!/usr/bin/env bash
set -euo pipefail

PYSIDE_VERSION="6.12.0"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETTINGS="${KEYMASTER_SETTINGS:-${XDG_CONFIG_HOME:-$HOME/.config}/keymaster/settings.json}"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"

setting() {
  [ -f "$SETTINGS" ] || return 0
  sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$SETTINGS" | head -n 1
}

explicit() {
  case "$1" in en|es-419) printf '%s' "$1" ;; esac
}

UI_LANG="$(explicit "${KEYMASTER_LANGUAGE:-}")"
[ -n "$UI_LANG" ] || UI_LANG="$(explicit "$(setting language)")"
if [ -z "$UI_LANG" ]; then
  case "${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}" in es*) UI_LANG="es-419" ;; *) UI_LANG="en" ;; esac
fi

msg() {
  local key="$1" text pair name value
  shift
  text="$(sed -n "s/^[[:space:]]*\"${key//./\\.}\"[[:space:]]*:[[:space:]]*\"\(.*\)\",\{0,1\}[[:space:]]*$/\1/p" "$APP_DIR/i18n/$UI_LANG.json" | head -n 1)"
  [ -n "$text" ] || text="$key"
  for pair in "$@"; do
    name="${pair%%=*}"
    value="${pair#*=}"
    text="${text//"{$name}"/"$value"}"
  done
  printf '%s' "$text"
}

say() {
  printf '%s\n' "$(msg "$@")"
}

PYTHON="${KEYMASTER_PYTHON:-$(setting python)}"
CORE="${KEYMASTER_CORE:-$(setting core)}"

if [ -z "$CORE" ] || [ ! -d "$CORE/keymaster" ]; then
  say "app.install.no_core" "path=$SETTINGS" >&2
  exit 1
fi
if [ -z "$PYTHON" ] || [ ! -x "$PYTHON" ]; then
  say "app.install.bad_python" "path=${PYTHON:-?}" >&2
  exit 1
fi

if "$PYTHON" -c "import sys, PySide6; sys.exit(PySide6.__version__ != '$PYSIDE_VERSION')" >/dev/null 2>&1; then
  say "app.install.already" "version=$PYSIDE_VERSION"
else
  say "app.install.installing" "version=$PYSIDE_VERSION"
  spec="PySide6-Essentials==$PYSIDE_VERSION"
  if "$PYTHON" -m pip --version >/dev/null 2>&1; then
    "$PYTHON" -m pip install --upgrade "$spec" || { say "app.install.pip_failed" >&2; exit 1; }
  elif command -v uv >/dev/null 2>&1; then
    uv pip install --python "$PYTHON" "$spec" || { say "app.install.pip_failed" >&2; exit 1; }
  else
    { "$PYTHON" -m ensurepip --upgrade && "$PYTHON" -m pip install --upgrade "$spec"; } || { say "app.install.pip_failed" >&2; exit 1; }
  fi
fi

mkdir -p "$BIN_DIR" "$DATA_DIR/applications" "$DATA_DIR/icons/hicolor/scalable/apps"
LAUNCHER="$BIN_DIR/keymaster-app"
cat > "$LAUNCHER" <<EOF
#!/bin/sh
PYTHONPATH="$APP_DIR\${PYTHONPATH:+:\$PYTHONPATH}" exec "$PYTHON" -m keymaster_app "\$@"
EOF
chmod +x "$LAUNCHER"
say "app.install.launcher" "path=$LAUNCHER"

cp "$APP_DIR/keymaster_app/assets/icon.svg" "$DATA_DIR/icons/hicolor/scalable/apps/keymaster-app.svg"
COMMENT_EN="$(UI_LANG=en msg "app.desktop.comment")"
COMMENT_ES="$(UI_LANG=es-419 msg "app.desktop.comment")"
cat > "$DATA_DIR/applications/keymaster-app.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Keymaster
Comment=$COMMENT_EN
Comment[es]=$COMMENT_ES
Comment[es_419]=$COMMENT_ES
Exec="$LAUNCHER" %F
Icon=keymaster-app
Terminal=false
Categories=AudioVideo;Video;Graphics;
StartupWMClass=keymaster-app
EOF
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q "$DATA_DIR/applications" || true
say "app.install.shortcut"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) say "app.install.not_in_path" "dir=$BIN_DIR" "path=$LAUNCHER" ;;
esac
say "app.install.done"
