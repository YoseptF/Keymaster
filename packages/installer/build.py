#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import generate

PAYLOAD_MARKER = "__KEYMASTER_PAYLOAD__"
GIT_REQUIREMENT = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*@\s*git\+\S+@([0-9a-f]{7,40})\s*$")


def version_of(name: str) -> str:
    return json.loads((ROOT / "packages" / name / "package.json").read_text(encoding="utf-8"))["version"]


def suffix_for(version: str) -> str:
    own = version_of("installer")
    return version[len(own):] if version.startswith(own) else ""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(url: str, expected: str, cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"{expected}-{url.rsplit('/', 1)[-1]}"
    if target.is_file() and sha256(target) == expected:
        return target
    print(f"downloading {url}", flush=True)
    partial = target.with_name(target.name + ".part")
    with urllib.request.urlopen(url) as response, open(partial, "wb") as out:
        shutil.copyfileobj(response, out)
    actual = sha256(partial)
    if actual != expected:
        partial.unlink()
        raise SystemExit(f"{url} has sha256 {actual}, expected {expected}")
    partial.replace(target)
    return target


def git_requirements() -> dict[str, str]:
    found = {}
    for line in (ROOT / "packages" / "core" / "upstream" / "requirements.txt").read_text(encoding="utf-8").splitlines():
        match = GIT_REQUIREMENT.match(line)
        if match:
            found[match.group(1)] = match.group(2)
    return found


def build_wheel(source: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if shutil.which("uv"):
        cmd = ["uv", "build", "--wheel", "--out-dir", str(out_dir), str(source)]
    else:
        cmd = [sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(out_dir), str(source)]
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def wheels(pins: dict, cache: Path, prebuilt: Path | None) -> list[Path]:
    found = []
    for name, commit in git_requirements().items():
        pin = pins["wheels"].get(name)
        if not pin or not pin["commit"].startswith(commit) and not commit.startswith(pin["commit"]):
            raise SystemExit(f"requirements.txt pins {name} at {commit}; update packages/installer/pins.json to match")
        pattern = f"{name.replace('-', '_')}-*.whl"
        if prebuilt and list(prebuilt.glob(pattern)):
            found.append(sorted(prebuilt.glob(pattern))[-1])
            continue
        built = cache / "wheels" / pin["commit"]
        if not list(built.glob(pattern)):
            build_wheel(fetch(pin["url"], pin["sha256"], cache), built)
        found.append(sorted(built.glob(pattern))[-1])
    return found


def artifact(name: str, platform: str | None, work: Path, suffix: str, prebuilt: Path | None) -> Path:
    tail = f"-{platform}.zip" if platform else ".zip"
    if prebuilt:
        matches = sorted(prebuilt.glob(f"keymaster-{name}-*{tail}"))
        if platform is None:
            matches = [m for m in matches if not m.name.endswith(("-linux.zip", "-windows.zip"))]
        if matches:
            return matches[-1]
    version = version_of(name) + suffix
    cmd = [sys.executable, str(ROOT / "packages" / name / "build.py"), "--out", str(work), "--version", version]
    if platform:
        cmd += ["--platform", platform]
    subprocess.run(cmd, check=True)
    return work / f"keymaster-{name}-{version}{tail}"


def extract(zip_path: Path, prefix: str, dest: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir() or not info.filename.startswith(prefix):
                continue
            rel = info.filename[len(prefix):]
            if not rel:
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))
            mode = (info.external_attr >> 16) & 0o777
            os.chmod(target, 0o755 if mode & 0o100 else 0o644)


def stage(platform: str, stage_dir: Path, work: Path, suffix: str, prebuilt: Path | None, wheel_files: list[Path]) -> None:
    extract(artifact("core", None, work, suffix, prebuilt), "keymaster-core/", stage_dir / "core")
    extract(artifact("app", None, work, suffix, prebuilt), "keymaster-app/", stage_dir / "app")
    (stage_dir / "blender").mkdir(parents=True)
    shutil.copy(artifact("blender", None, work, suffix, prebuilt), stage_dir / "blender" / "keymaster-blender.zip")
    extract(artifact("openfx", platform, work, suffix, prebuilt), "Keymaster.ofx.bundle/", stage_dir / "openfx" / "Keymaster.ofx.bundle")
    (stage_dir / "wheels").mkdir()
    for wheel in wheel_files:
        shutil.copy(wheel, stage_dir / "wheels" / wheel.name)
    if platform == "windows":
        extract(artifact("adobe", None, work, suffix, prebuilt), "keymaster-adobe/com.keymaster.adobe/", stage_dir / "adobe" / "com.keymaster.adobe")


def tar_payload(stage_dir: Path) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.PAX_FORMAT) as tar:
        for path in sorted(stage_dir.rglob("*")):
            info = tar.gettarinfo(str(path), path.relative_to(stage_dir).as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            if info.isfile():
                with open(path, "rb") as f:
                    tar.addfile(info, f)
            else:
                tar.addfile(info)
    return buffer.getvalue()


def linux_header(version: str, pins: dict) -> str:
    body = (HERE / "linux" / "installer.sh").read_text(encoding="utf-8")
    if body.startswith("#!"):
        body = body.split("\n", 1)[1]
    values = {
        "KM_VERSION": version,
        "KM_UV_VERSION": pins["uv"]["version"],
        "KM_UV_URL": pins["uv"]["linux"]["url"],
        "KM_UV_SHA256": pins["uv"]["linux"]["sha256"],
        "KM_FFMPEG_URL": pins["ffmpeg"]["linux"]["url"],
        "KM_FFMPEG_SHA256": pins["ffmpeg"]["linux"]["sha256"],
        "KM_FFMPEG_LICENSE_URL": pins["ffmpeg"]["linux"]["license_url"],
        "KM_FFMPEG_LICENSE_SHA256": pins["ffmpeg"]["linux"]["license_sha256"],
    }
    return "#!/usr/bin/env bash\n" + generate.bash_vars(values) + generate.bash_messages(generate.load_tables()) + body


def build_linux(out: Path, version: str, stage_dir: Path, pins: dict) -> Path:
    target = out / f"keymaster-installer-{version}-linux.sh"
    header = linux_header(version, pins)
    with open(target, "wb") as f:
        f.write(header.encode("utf-8"))
        f.write(f"{PAYLOAD_MARKER}\n".encode("ascii"))
        f.write(tar_payload(stage_dir))
    os.chmod(target, 0o755)
    return target


def uv_exe(pins: dict, cache: Path, dest: Path) -> None:
    archive = fetch(pins["uv"]["windows"]["url"], pins["uv"]["windows"]["sha256"], cache)
    with zipfile.ZipFile(archive) as zf:
        name = next(n for n in zf.namelist() if n.rsplit("/", 1)[-1] == "uv.exe")
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "uv.exe").write_bytes(zf.read(name))


def write_bom(path: Path, text: str) -> None:
    path.write_text("﻿" + text, encoding="utf-8")


def build_windows(out: Path, version: str, stage_dir: Path, pins: dict, cache: Path, work: Path) -> Path:
    makensis = shutil.which("makensis")
    if not makensis:
        raise SystemExit("makensis is needed to build the Windows installer (apt install nsis)")
    uv_exe(pins, cache, stage_dir / "bin")
    shutil.copy(HERE / "windows" / "core-step.ps1", stage_dir / "core-step.ps1")
    generated = work / "nsis"
    generated.mkdir()
    write_bom(generated / "lang.nsh", generate.nsis_langstrings(generate.load_tables()))
    ffmpeg = pins["ffmpeg"]["windows"]
    numeric = ".".join((re.findall(r"\d+", version) + ["0", "0", "0"])[:3]) + ".0"
    write_bom(generated / "defines.nsh", generate.nsis_defines({
        "KM_VERSION": version,
        "KM_VERSION_NUMERIC": numeric,
        "KM_FFMPEG_URL": ffmpeg["url"],
        "KM_FFMPEG_SHA256": ffmpeg["sha256"],
        "KM_STAGE": str(stage_dir),
        "KM_GENERATED": str(generated),
    }))
    target = (out / f"keymaster-installer-{version}-windows.exe").resolve()
    cmd = [makensis, "-V2", "-INPUTCHARSET", "UTF8", f"-DKM_DEFINES={generated / 'defines.nsh'}",
           f"-DKM_OUTFILE={target}", str(HERE / "windows" / "keymaster.nsi")]
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
    return target


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--platform", choices=("linux", "windows"), default="windows" if sys.platform == "win32" else "linux")
    ap.add_argument("--prebuilt", help="folder with already built package zips and wheels to embed instead of building them")
    ap.add_argument("--pins", default=str(HERE / "pins.json"))
    ap.add_argument("--cache", default=os.environ.get("KEYMASTER_INSTALLER_CACHE", str(ROOT / "tmp" / "installer-cache")))
    args = ap.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    pins = generate.load_pins(Path(args.pins))
    cache = Path(args.cache).resolve()
    prebuilt = Path(args.prebuilt).resolve() if args.prebuilt else None
    suffix = suffix_for(args.version)
    with tempfile.TemporaryDirectory(prefix="keymaster-installer-") as tmp:
        work = Path(tmp)
        stage_dir = work / "stage"
        stage(args.platform, stage_dir, work, suffix, prebuilt, wheels(pins, cache, prebuilt))
        if args.platform == "linux":
            target = build_linux(out, args.version, stage_dir, pins)
        else:
            target = build_windows(out, args.version, stage_dir, pins, cache, work)
    print(target)


if __name__ == "__main__":
    main()
