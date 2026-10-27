#!/usr/bin/env bash
set -euo pipefail

KM_SELF="$(readlink -f "${BASH_SOURCE[0]}")"
PAYLOAD_MARKER="__KEYMASTER_PAYLOAD__"
STATE_NAME=".keymaster-install"
SETTINGS="${KEYMASTER_SETTINGS:-${XDG_CONFIG_HOME:-$HOME/.config}/keymaster/settings.json}"
DEFAULT_PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}/keymaster"
SUDO="${KEYMASTER_INSTALLER_SUDO:-sudo}"
NEEDED_GB=15

setting() {
  [ -f "$SETTINGS" ] || return 0
  sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$SETTINGS" | head -n 1
}

explicit() {
  case "$1" in en|es-419) printf '%s' "$1" ;; esac
}

os_language() {
  local var value
  for var in LC_ALL LC_MESSAGES LANG; do
    value="${!var:-}"
    case "$value" in ""|C|POSIX|C.*|POSIX.*) continue ;; esac
    printf '%s' "$value"
    return
  done
}

UI_LANG="$(explicit "${KEYMASTER_LANGUAGE:-}")"
[ -n "$UI_LANG" ] || UI_LANG="$(explicit "$(setting language)")"
if [ -z "$UI_LANG" ]; then
  case "$(os_language)" in es*) UI_LANG="es-419" ;; *) UI_LANG="en" ;; esac
fi

msg() {
  local key="$1" text pair name value
  shift
  text="${KM_TEXT[$UI_LANG:$key]:-${KM_TEXT[en:$key]:-$key}}"
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

INTERACTIVE=0
[ -t 0 ] && [ -t 1 ] && INTERACTIVE=1
ASSUME_YES=0
COMPONENTS=""
PREFIX=""
BUNDLED_FFMPEG=0
MODE=install

ask() {
  local question="$1" default="$2" hint answer
  if [ "$INTERACTIVE" -ne 1 ] || [ "$ASSUME_YES" -eq 1 ]; then
    [ "$default" = yes ]
    return
  fi
  if [ "$default" = yes ]; then hint="$(msg "installer.prompt.default_yes")"; else hint="$(msg "installer.prompt.default_no")"; fi
  printf '%s %s ' "$question" "$hint"
  read -r answer || answer=""
  answer="$(printf '%s' "$answer" | tr '[:upper:]' '[:lower:]')"
  case "$answer" in
    "") [ "$default" = yes ] ;;
    y|yes|s|si|sí) return 0 ;;
    *) return 1 ;;
  esac
}

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      -y|--yes) ASSUME_YES=1 ;;
      --components) shift; COMPONENTS="${1:-}" ;;
      --components=*) COMPONENTS="${1#*=}" ;;
      --prefix) shift; PREFIX="${1:-}" ;;
      --prefix=*) PREFIX="${1#*=}" ;;
      --bundled-ffmpeg) BUNDLED_FFMPEG=1 ;;
      --uninstall) MODE=uninstall ;;
      -h|--help) MODE=help ;;
      *) say "installer.error.bad_option" "name=$1" >&2; exit 2 ;;
    esac
    shift
  done
  if [ -z "$PREFIX" ]; then
    if [ -f "$(dirname "$KM_SELF")/$STATE_NAME" ]; then PREFIX="$(dirname "$KM_SELF")"; else PREFIX="$DEFAULT_PREFIX"; fi
  fi
  PREFIX="$(readlink -m "$PREFIX")"
}

payload_line() {
  grep -an -m 1 "^${PAYLOAD_MARKER}\$" "$KM_SELF" | cut -d: -f1 || true
}

download() {
  local url="$1" out="$2" sha="$3"
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 --progress-bar -o "$out" "$url" || { say "installer.error.download" >&2; exit 1; }
  elif command -v wget >/dev/null 2>&1; then
    wget -q --show-progress -O "$out" "$url" || { say "installer.error.download" >&2; exit 1; }
  else
    say "installer.error.no_download_tool" >&2
    exit 1
  fi
  if ! printf '%s  %s\n' "$sha" "$out" | sha256sum -c --quiet - >/dev/null 2>&1; then
    rm -f "$out"
    say "installer.error.checksum" >&2
    exit 1
  fi
}

gpu_name() {
  command -v nvidia-smi >/dev/null 2>&1 || return 0
  nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n 1 || true
}

blender_candidates() {
  if [ -n "${KEYMASTER_INSTALLER_BLENDER+set}" ]; then
    tr ':' '\n' <<<"$KEYMASTER_INSTALLER_BLENDER" | sed '/^$/d'
    return
  fi
  command -v blender 2>/dev/null || true
  local p
  for p in /snap/bin/blender "$HOME/.local/share/Steam/steamapps/common/Blender/blender" \
           "$HOME/.steam/steam/steamapps/common/Blender/blender" /opt/blender*/blender /usr/local/blender*/blender \
           "$HOME"/blender*/blender "$HOME"/Applications/blender*/blender; do
    [ -x "$p" ] && printf '%s\n' "$p"
  done
  return 0
}

detect_blenders() {
  BLENDERS=()
  local exe version seen=""
  while IFS= read -r exe; do
    [ -x "$exe" ] || continue
    case " $seen " in *" $(readlink -f "$exe") "*) continue ;; esac
    seen="$seen $(readlink -f "$exe")"
    version="$("$exe" --version 2>/dev/null | sed -n 's/^Blender \([0-9][0-9]*\.[0-9][0-9]*\).*/\1/p' | head -n 1 || true)"
    [ -n "$version" ] || continue
    if [ "${version%%.*}" -lt 5 ]; then
      say "installer.blender.too_old" "version=$version"
      continue
    fi
    BLENDERS+=("$exe|$version")
  done < <(blender_candidates)
}

detect_ofx_host() {
  local p list
  if [ -n "${KEYMASTER_INSTALLER_OFX_HOSTS+set}" ]; then
    list="$(tr ':' '\n' <<<"$KEYMASTER_INSTALLER_OFX_HOSTS")"
  else
    list="$(printf '%s\n' /opt/resolve/bin/resolve /usr/local/Nuke*/Nuke* /opt/Nuke*/Nuke* /opt/Foundry/Nuke*/Nuke*)"
  fi
  while IFS= read -r p; do
    [ -n "$p" ] && [ -e "$p" ] && return 0
  done <<<"$list"
  return 1
}

choose_components() {
  WANT_APP=1
  WANT_BLENDER=0
  WANT_OPENFX=0
  [ ${#BLENDERS[@]} -gt 0 ] && WANT_BLENDER=1
  detect_ofx_host && WANT_OPENFX=1
  if [ -n "$COMPONENTS" ]; then
    WANT_APP=0
    WANT_BLENDER=0
    WANT_OPENFX=0
    local item
    for item in ${COMPONENTS//,/ }; do
      case "$item" in
        core) ;;
        app) WANT_APP=1 ;;
        blender) WANT_BLENDER=1 ;;
        openfx) WANT_OPENFX=1 ;;
        *) say "installer.error.bad_component" "name=$item" >&2; exit 2 ;;
      esac
    done
  elif [ "$INTERACTIVE" -eq 1 ] && [ "$ASSUME_YES" -eq 0 ]; then
    ask "$(msg "installer.prompt.component" "name=$(msg "installer.component.app")")" yes || WANT_APP=0
    if [ ${#BLENDERS[@]} -gt 0 ]; then
      ask "$(msg "installer.prompt.component" "name=$(msg "installer.component.blender")")" yes || WANT_BLENDER=0
    fi
    if [ "$WANT_OPENFX" -eq 1 ]; then
      ask "$(msg "installer.prompt.component" "name=$(msg "installer.component.openfx")")" yes || WANT_OPENFX=0
    else
      ask "$(msg "installer.prompt.component" "name=$(msg "installer.component.openfx") $(msg "installer.component.not_found")")" no && WANT_OPENFX=1
    fi
  fi
  if [ "$WANT_BLENDER" -eq 1 ] && [ ${#BLENDERS[@]} -eq 0 ]; then
    say "installer.blender.none"
    WANT_BLENDER=0
  fi
}

component_list() {
  local names
  names="$(msg "installer.component.core")"
  [ "$WANT_APP" -eq 1 ] && names="$names, $(msg "installer.component.app")"
  [ "$WANT_BLENDER" -eq 1 ] && names="$names, $(msg "installer.component.blender")"
  [ "$WANT_OPENFX" -eq 1 ] && names="$names, $(msg "installer.component.openfx")"
  printf '%s' "$names"
}

record() {
  printf '%s=%s\n' "$1" "$2" >> "$PREFIX/$STATE_NAME"
}

new_dirs() {
  local dir
  for dir in "$@"; do
    while [ ! -e "$dir" ] && [ "$dir" != / ]; do
      printf '%s\n' "$dir"
      dir="$(dirname "$dir")"
    done
  done
}

record_dirs() {
  local dir
  while IFS= read -r dir; do
    [ -n "$dir" ] && record dir "$dir"
  done <<<"$1"
  return 0
}

free_gb() {
  local dir="$1"
  while [ ! -d "$dir" ]; do dir="$(dirname "$dir")"; done
  df -Pk "$dir" | awk 'NR == 2 {printf "%d", $4 / 1048576}'
}

check_disk() {
  [ -x "$PREFIX/core/.venv/bin/python" ] && return 0
  local free
  free="$(free_gb "$PREFIX")"
  [ "$free" -ge "$NEEDED_GB" ] && return 0
  say "installer.error.disk" "free=$free" "dir=$PREFIX" >&2
  if [ "$INTERACTIVE" -eq 1 ] && [ "$ASSUME_YES" -eq 0 ] && ! ask "$(msg "installer.prompt.continue")" no; then
    say "installer.cancelled"
    exit 1
  fi
}

copy_files() {
  local stage="$1" line="$2"
  say "installer.step.files"
  mkdir -p "$PREFIX/core"
  find "$PREFIX/core" -mindepth 1 -maxdepth 1 ! -name .venv ! -name upstream -exec rm -rf {} +
  if [ -d "$PREFIX/core/upstream" ]; then
    find "$PREFIX/core/upstream" -mindepth 1 -maxdepth 1 ! -name weights ! -name vfms -exec rm -rf {} +
  fi
  cp -a "$stage/core/." "$PREFIX/core/"
  rm -rf "$PREFIX/wheels"
  cp -a "$stage/wheels" "$PREFIX/wheels"
  if [ "$WANT_APP" -eq 1 ]; then
    rm -rf "$PREFIX/app"
    cp -a "$stage/app" "$PREFIX/app"
  fi
  if [ "$WANT_BLENDER" -eq 1 ]; then
    mkdir -p "$PREFIX/blender"
    cp "$stage/blender/keymaster-blender.zip" "$PREFIX/blender/"
  fi
  if [ "$WANT_OPENFX" -eq 1 ]; then
    rm -rf "$PREFIX/openfx"
    cp -a "$stage/openfx" "$PREFIX/openfx"
  fi
  head -n "$((line - 1))" "$KM_SELF" > "$PREFIX/uninstall.sh"
  chmod 755 "$PREFIX/uninstall.sh"
}

ensure_uv() {
  local wanted="${KEYMASTER_INSTALLER_UV:-}"
  if [ "$wanted" != download ]; then
    if [ -n "$wanted" ]; then
      mkdir -p "$PREFIX/bin"
      ln -sf "$wanted" "$PREFIX/bin/uv"
      return
    fi
    command -v uv >/dev/null 2>&1 && return
  fi
  [ -x "$PREFIX/bin/uv" ] && [ ! -L "$PREFIX/bin/uv" ] && return
  say "installer.step.uv" "version=$KM_UV_VERSION"
  local work found
  work="$(mktemp -d)"
  download "${KEYMASTER_INSTALLER_UV_URL:-$KM_UV_URL}" "$work/uv.tar.gz" "${KEYMASTER_INSTALLER_UV_SHA256:-$KM_UV_SHA256}"
  mkdir -p "$work/x" "$PREFIX/bin"
  tar xzf "$work/uv.tar.gz" -C "$work/x"
  found="$(find "$work/x" -type f -name uv | head -n 1)"
  rm -f "$PREFIX/bin/uv"
  install -m 755 "$found" "$PREFIX/bin/uv"
  rm -rf "$work"
}

ensure_ffmpeg() {
  FFMPEG_SETTING=""
  local system
  system="$(command -v ffmpeg 2>/dev/null || true)"
  if [ "$BUNDLED_FFMPEG" -eq 0 ] && [ -n "$system" ] && [ "$system" != "$PREFIX/ffmpeg/ffmpeg" ]; then
    say "installer.step.ffmpeg_system" "path=$system"
    return
  fi
  FFMPEG_SETTING="$PREFIX/ffmpeg/ffmpeg"
  [ -x "$FFMPEG_SETTING" ] && return
  say "installer.step.ffmpeg"
  local work
  work="$(mktemp -d)"
  download "${KEYMASTER_INSTALLER_FFMPEG_URL:-$KM_FFMPEG_URL}" "$work/ffmpeg.gz" "${KEYMASTER_INSTALLER_FFMPEG_SHA256:-$KM_FFMPEG_SHA256}"
  mkdir -p "$PREFIX/ffmpeg"
  gunzip -c "$work/ffmpeg.gz" > "$FFMPEG_SETTING"
  chmod 755 "$FFMPEG_SETTING"
  rm -rf "$work"
}

run_logged() {
  if [ "$INTERACTIVE" -eq 1 ] && command -v script >/dev/null 2>&1; then
    script -qefa -c "$(printf '%q ' "$@")" "$LOG"
    return
  fi
  "$@" 2>&1 | tee -a "$LOG"
}

install_core() {
  local own_cache=0
  export PATH="$PREFIX/bin:$PATH"
  export UV_PYTHON_INSTALL_DIR="$PREFIX/python"
  export UV_PYTHON_PREFERENCE=only-managed
  export KEYMASTER_WHEELS="$PREFIX/wheels"
  if [ -z "${UV_CACHE_DIR:-}" ]; then
    export UV_CACHE_DIR="$PREFIX/cache"
    own_cache=1
  fi
  say "installer.step.core"
  if ! run_logged bash "$PREFIX/core/install.sh"; then
    say "installer.error.core" "log=$LOG" >&2
    exit 1
  fi
  [ "$own_cache" -eq 1 ] && rm -rf "$PREFIX/cache"
  say "installer.step.settings"
  (
    cd "$PREFIX/core"
    "$PY" -m keymaster settings set python "$PY" >/dev/null
    "$PY" -m keymaster settings set core "$PREFIX/core" >/dev/null
    if [ -n "$FFMPEG_SETTING" ]; then
      "$PY" -m keymaster settings set ffmpeg "$FFMPEG_SETTING" >/dev/null
    fi
  )
}

install_app() {
  say "installer.step.app"
  local bin_dir="${XDG_BIN_HOME:-$HOME/.local/bin}" data_dir="${XDG_DATA_HOME:-$HOME/.local/share}"
  record_dirs "$(new_dirs "$bin_dir" "$data_dir/applications" "$data_dir/icons/hicolor/scalable/apps")"
  if ! bash "$PREFIX/app/install.sh" 2>&1 | tee -a "$LOG"; then
    say "installer.error.app" "log=$LOG" >&2
    APP_FAILED=1
    return
  fi
  record file "$bin_dir/keymaster-app"
  record file "$data_dir/applications/keymaster-app.desktop"
  record file "$data_dir/icons/hicolor/scalable/apps/keymaster-app.svg"
  record desktop_db "$data_dir/applications"
  APP_LAUNCHER="$bin_dir/keymaster-app"
}

install_blender() {
  local entry exe version ext
  for entry in "${BLENDERS[@]}"; do
    exe="${entry%%|*}"
    version="${entry#*|}"
    say "installer.step.blender" "version=$version"
    if "$exe" --command extension install-file -r user_default -e "$PREFIX/blender/keymaster-blender.zip" >>"$LOG" 2>&1; then
      ext="$("$exe" --background --factory-startup --python-expr \
        'import bpy; print("KEYMASTER_EXTENSIONS=" + bpy.utils.user_resource("EXTENSIONS", path="user_default"))' 2>/dev/null \
        | sed -n 's/^KEYMASTER_EXTENSIONS=//p' | head -n 1 || true)"
      record blender "$exe|$ext"
    else
      say "installer.blender.failed" "version=$version" >&2
    fi
  done
}

can_sudo() {
  command -v "$SUDO" >/dev/null 2>&1 || return 1
  "$SUDO" -n true >/dev/null 2>&1 && return 0
  [ "$INTERACTIVE" -eq 1 ]
}

install_openfx() {
  local dest="${OFX_PLUGIN_DIR:-/usr/OFX/Plugins}" src="$PREFIX/openfx/Keymaster.ofx.bundle"
  local command="$SUDO mkdir -p '$dest' && $SUDO rm -rf '$dest/Keymaster.ofx.bundle' && $SUDO cp -R '$src' '$dest/'"
  say "installer.step.openfx" "dir=$dest"
  local created
  created="$(new_dirs "$dest")"
  if mkdir -p "$dest" 2>/dev/null && [ -w "$dest" ]; then
    record_dirs "$created"
    rm -rf "$dest/Keymaster.ofx.bundle"
    cp -R "$src" "$dest/"
  elif can_sudo; then
    say "installer.openfx.needs_admin" "dir=$dest"
    if ! { "$SUDO" mkdir -p "$dest" && "$SUDO" rm -rf "$dest/Keymaster.ofx.bundle" && "$SUDO" cp -R "$src" "$dest/"; }; then
      say "installer.openfx.skipped" "command=$command"
      return
    fi
  else
    say "installer.openfx.skipped" "command=$command"
    return
  fi
  record openfx "$dest/Keymaster.ofx.bundle"
  OPENFX_DONE=1
}

run_doctor() {
  say "installer.step.doctor"
  local report failing
  report="$(cd "$PREFIX/core" && "$PY" -m keymaster doctor --json 2>>"$LOG" || true)"
  failing="$(printf '%s\n' "$report" | "$PY" -c 'import json, sys
lines = [l for l in sys.stdin.read().splitlines() if l.strip()]
report = json.loads(lines[-1]) if lines else {"checks": [{"id": "doctor", "ok": False}]}
print(", ".join(c["id"] for c in report.get("checks", []) if not c.get("ok")))' 2>/dev/null || printf 'doctor')"
  if [ -z "$failing" ]; then
    say "installer.done.ok"
  else
    say "installer.done.problems" "checks=$failing"
  fi
}

do_install() {
  [ "$(uname -m)" = x86_64 ] || { say "installer.error.arch" >&2; exit 1; }
  local line
  line="$(payload_line)"
  [ -n "$line" ] || { MODE=uninstall; do_uninstall; return; }
  say "installer.welcome.linux" "version=$KM_VERSION"
  local gpu
  gpu="$(gpu_name)"
  if [ -n "$gpu" ]; then
    say "installer.gpu.found" "name=$gpu"
  else
    say "installer.gpu.missing" >&2
    if [ "$INTERACTIVE" -eq 1 ] && [ "$ASSUME_YES" -eq 0 ] && ! ask "$(msg "installer.prompt.continue")" no; then
      say "installer.cancelled"
      exit 1
    fi
  fi
  detect_blenders
  choose_components
  say "installer.summary.dir" "dir=$PREFIX"
  say "installer.summary.components" "list=$(component_list)"
  if [ "$INTERACTIVE" -eq 1 ] && [ "$ASSUME_YES" -eq 0 ] && ! ask "$(msg "installer.prompt.install" "dir=$PREFIX")" yes; then
    say "installer.cancelled"
    exit 1
  fi
  check_disk

  local previous="" created
  created="$(new_dirs "$PREFIX" "$(dirname "$SETTINGS")")"
  STAGE="$(mktemp -d)"
  trap 'rm -rf "$STAGE"' EXIT
  tail -n +"$((line + 1))" "$KM_SELF" | tar xzf - -C "$STAGE"
  [ -f "$PREFIX/$STATE_NAME" ] && previous="$(grep -v '^version=' "$PREFIX/$STATE_NAME" || true)"
  mkdir -p "$PREFIX/logs"
  LOG="$PREFIX/logs/install.log"
  : > "$LOG"
  copy_files "$STAGE" "$line"
  { printf 'version=%s\n' "$KM_VERSION"; [ -n "$previous" ] && printf '%s\n' "$previous"; } > "$PREFIX/$STATE_NAME"
  record_dirs "$created"
  if [ ! -f "$SETTINGS" ] && ! grep -qxF "settings_created=$SETTINGS" "$PREFIX/$STATE_NAME"; then
    record settings_created "$SETTINGS"
  fi

  PY="$PREFIX/core/.venv/bin/python"
  ensure_uv
  ensure_ffmpeg
  install_core
  APP_FAILED=0
  APP_LAUNCHER=""
  OPENFX_DONE=0
  [ "$WANT_APP" -eq 1 ] && install_app
  [ "$WANT_BLENDER" -eq 1 ] && install_blender
  [ "$WANT_OPENFX" -eq 1 ] && install_openfx
  sort -u -o "$PREFIX/$STATE_NAME" "$PREFIX/$STATE_NAME"
  run_doctor
  [ -n "$APP_LAUNCHER" ] && say "installer.next.app" "command=$APP_LAUNCHER"
  [ "$WANT_BLENDER" -eq 1 ] && say "installer.next.blender"
  [ "$OPENFX_DONE" -eq 1 ] && say "installer.next.openfx"
  say "installer.next.uninstall" "command=bash $PREFIX/uninstall.sh"
  [ "$APP_FAILED" -eq 0 ]
}

remove_root_path() {
  local path="$1"
  [ -e "$path" ] || return 0
  rm -rf "$path" 2>/dev/null && [ ! -e "$path" ] && return 0
  if can_sudo && "$SUDO" rm -rf "$path"; then
    return 0
  fi
  say "installer.uninstall.openfx_left" "dir=$(dirname "$path")" "command=$SUDO rm -rf '$path'"
}

do_uninstall() {
  local state="$PREFIX/$STATE_NAME"
  if [ ! -f "$state" ]; then
    say "installer.uninstall.not_found" "dir=$PREFIX" >&2
    exit 1
  fi
  if [ "$INTERACTIVE" -eq 1 ] && [ "$ASSUME_YES" -eq 0 ] && ! ask "$(msg "installer.uninstall.confirm" "dir=$PREFIX")" no; then
    exit 1
  fi
  local key value exe ext
  while IFS='=' read -r key value; do
    case "$key" in
      blender)
        exe="${value%%|*}"
        ext="${value#*|}"
        if [ -x "$exe" ]; then "$exe" --command extension remove keymaster >/dev/null 2>&1 || true; fi
        [ -n "$ext" ] && rm -rf "$ext/keymaster"
        ;;
      openfx) remove_root_path "$value" ;;
      file) rm -f "$value" ;;
      desktop_db)
        if command -v update-desktop-database >/dev/null 2>&1; then update-desktop-database -q "$value" 2>/dev/null || true; fi
        ;;
      settings_created) rm -f "$value" ;;
    esac
  done < "$state"
  cd /
  local dirs
  dirs="$(sed -n 's/^dir=//p' "$state" | awk '{print length, $0}' | sort -rn | cut -d' ' -f2-)"
  rm -rf "$PREFIX"
  while IFS= read -r value; do
    [ -d "$value" ] || continue
    [ "$(ls -A "$value")" = mimeinfo.cache ] && rm -f "$value/mimeinfo.cache"
    rmdir "$value" 2>/dev/null || true
  done <<<"$dirs"
  say "installer.uninstall.done"
}

main() {
  parse_args "$@"
  case "$MODE" in
    help) say "installer.help" "program=$(basename "$KM_SELF")" "prefix=$DEFAULT_PREFIX" ;;
    uninstall) do_uninstall ;;
    *) do_install ;;
  esac
}

main "$@"
exit $?
