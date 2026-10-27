#!/usr/bin/env sh
set -eu
here=$(cd "$(dirname "$0")" && pwd)
dest=${OFX_PLUGIN_DIR:-/usr/OFX/Plugins}
lang=${KEYMASTER_LANGUAGE:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}

say() {
  case "$lang" in
    es*) printf '%s\n' "$2" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif mkdir -p "$dest" 2>/dev/null && [ -w "$dest" ]; then
    "$@"
  else
    sudo "$@"
  fi
}

if [ ! -d "$here/Keymaster.ofx.bundle" ]; then
  say "Keymaster.ofx.bundle was not found next to this script." "No se encontró Keymaster.ofx.bundle junto a este script."
  exit 1
fi
as_root mkdir -p "$dest"
as_root rm -rf "$dest/Keymaster.ofx.bundle"
as_root cp -R "$here/Keymaster.ofx.bundle" "$dest/"
say "Keymaster is installed in $dest/Keymaster.ofx.bundle. Restart DaVinci Resolve or Nuke to load it." \
    "Keymaster quedó instalado en $dest/Keymaster.ofx.bundle. Reinicia DaVinci Resolve o Nuke para cargarlo."
