from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
FAKE_CORE = ROOT / "packages" / "core" / "testing" / "fake_core"
TEST_VERSION = "0.0.0-test.1"

FAKE_UV = """#!/bin/sh
printf 'uv %s\\n' "$*" >> "$KM_LOG"
if [ -n "${KM_FAKE_UV_FAIL:-}" ] && [ "$1" = pip ]; then exit 1; fi
if [ "$1" = venv ]; then
  mkdir -p "$4/bin"
  cat > "$4/bin/python" <<EOF
#!/bin/sh
printf 'python %s\\\\n' "\\$*" >> "\\$KM_LOG"
if [ "\\$1" = -m ] && [ "\\$2" = keymaster ]; then shift 2; cd "\\$KM_FAKE_CORE" && exec "\\$KM_PY" -m keymaster "\\$@"; fi
if [ "\\$1" = -m ] && [ "\\$2" = pip ]; then exit 1; fi
case "\\$2" in *version_info*) exit 0 ;; esac
exec "\\$KM_PY" "\\$@"
EOF
  chmod +x "$4/bin/python"
fi
if [ "$1" = pip ]; then
  while [ $# -gt 0 ]; do
    if [ "$1" = -r ]; then sed 's/^/  | /' "$2" >> "$KM_LOG"; fi
    shift
  done
fi
exit 0
"""

FAKE_BLENDER = """#!/bin/sh
VERSION="${KM_BLENDER_VERSION:-5.1.2}"
ROOT="${BLENDER_USER_RESOURCES:?}"
printf 'blender %s\\n' "$*" >> "$KM_LOG"
case "$*" in
  --version) echo "Blender $VERSION"; echo "	build date: 2026-01-01" ;;
  *"extension install-file"*)
    for last in "$@"; do :; done
    mkdir -p "$ROOT/extensions/user_default/keymaster"
    "$KM_PY" -m zipfile -e "$last" "$ROOT/extensions/user_default/keymaster" ;;
  *"--python-expr"*) echo "KEYMASTER_EXTENSIONS=$ROOT/extensions/user_default" ;;
  *"extension remove keymaster"*) rm -rf "$ROOT/extensions/user_default/keymaster" ;;
esac
"""


def executable(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fake_openfx_zip(dest: Path, platform: str) -> Path:
    arch = {"linux": "Linux-x86-64", "windows": "Win64"}[platform]
    path = dest / f"keymaster-openfx-{TEST_VERSION}-{platform}.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"Keymaster.ofx.bundle/Contents/{arch}/Keymaster.ofx", b"fake plugin")
        zf.writestr("Keymaster.ofx.bundle/Contents/Resources/THIRD_PARTY_LICENSES.txt", "licenses")
        zf.writestr("README.md", "readme")
    return path


def prebuilt_dir(dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    fake_openfx_zip(dest, "linux")
    fake_openfx_zip(dest, "windows")
    with zipfile.ZipFile(dest / "utils3d-1.7-py3-none-any.whl", "w") as zf:
        zf.writestr("utils3d/__init__.py", "")
    return dest


def fake_downloads(dest: Path) -> dict[str, str]:
    dest.mkdir(parents=True, exist_ok=True)
    uv_tar = dest / "uv-x86_64-unknown-linux-musl.tar.gz"
    with tarfile.open(uv_tar, "w:gz") as tar:
        data = FAKE_UV.encode("utf-8")
        info = tarfile.TarInfo("uv-x86_64-unknown-linux-musl/uv")
        info.size = len(data)
        info.mode = 0o755
        tar.addfile(info, io.BytesIO(data))
    ffmpeg_gz = dest / "ffmpeg-linux-x64.gz"
    ffmpeg_gz.write_bytes(gzip.compress(b"#!/bin/sh\necho fake ffmpeg\n"))
    uv_zip = dest / "uv-x86_64-pc-windows-msvc.zip"
    with zipfile.ZipFile(uv_zip, "w") as zf:
        zf.writestr("uv.exe", b"MZ fake uv")
    return {
        "KEYMASTER_INSTALLER_UV_URL": uv_tar.as_uri(),
        "KEYMASTER_INSTALLER_UV_SHA256": sha256(uv_tar),
        "KEYMASTER_INSTALLER_FFMPEG_URL": ffmpeg_gz.as_uri(),
        "KEYMASTER_INSTALLER_FFMPEG_SHA256": sha256(ffmpeg_gz),
        "uv_zip_url": uv_zip.as_uri(),
        "uv_zip_sha256": sha256(uv_zip),
    }


def test_pins(dest: Path, downloads: dict[str, str]) -> Path:
    pins = json.loads((PACKAGE / "pins.json").read_text(encoding="utf-8"))
    pins["uv"]["windows"] = {"url": downloads["uv_zip_url"], "sha256": downloads["uv_zip_sha256"]}
    path = dest / "pins.json"
    path.write_text(json.dumps(pins), encoding="utf-8")
    return path


def build(out: Path, platform: str, prebuilt: Path, pins: Path, cache: Path) -> Path:
    cmd = [sys.executable, str(PACKAGE / "build.py"), "--out", str(out), "--version", TEST_VERSION,
           "--platform", platform, "--prebuilt", str(prebuilt), "--pins", str(pins), "--cache", str(cache)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    suffix = "linux.sh" if platform == "linux" else "windows.exe"
    return out / f"keymaster-installer-{TEST_VERSION}-{suffix}"


class Workspace:
    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="keymaster-installer-test-"))
        self.downloads = fake_downloads(self.root / "downloads")
        self.prebuilt = prebuilt_dir(self.root / "prebuilt")
        self.pins = test_pins(self.root, self.downloads)
        self.linux = build(self.root / "dist", "linux", self.prebuilt, self.pins, self.root / "cache")

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
