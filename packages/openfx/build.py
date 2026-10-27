#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARCH_DIRS = {"linux": "Linux-x86-64", "windows": "Win64"}
INSTALLERS = {"linux": "install.sh", "windows": "install.ps1"}
SYSTEM_DLLS = re.compile(r"^(kernel32|msvcrt|ucrtbase|advapi32|user32|shell32|ole32|bcrypt|ntdll|ws2_32|api-ms-win-[a-z0-9-]+)\.dll$", re.I)
NOTICES = [
    ("OpenFX", "vendor/openfx/LICENSE.md"),
    ("nlohmann/json", "vendor/nlohmann/LICENSE.MIT"),
    ("tinyexr", "vendor/tinyexr/LICENSE"),
    ("miniz", "vendor/miniz/LICENSE"),
]


def run(cmd: list[str]) -> None:
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def stb_license() -> str:
    text = (HERE / "vendor/stb/stb_image.h").read_text(encoding="utf-8")
    start = text.rfind("This software is available under 2 licenses")
    return text[start:].strip().rstrip("*/").strip() if start >= 0 else ""


def notices() -> str:
    parts = [f"== {name} ==\n\n{(HERE / rel).read_text(encoding='utf-8').strip()}\n" for name, rel in NOTICES]
    parts.append(f"== stb_image ==\n\n{stb_license()}\n")
    return "\n".join(parts)


def check_imports(dll: Path) -> None:
    objdump = shutil.which("x86_64-w64-mingw32-objdump") or shutil.which("objdump")
    if not objdump:
        raise SystemExit("objdump is needed to check the Windows plugin's imports")
    out = subprocess.run([objdump, "-p", str(dll)], check=True, capture_output=True, text=True).stdout
    names = re.findall(r"DLL Name:\s*(\S+)", out)
    bad = [n for n in names if not SYSTEM_DLLS.match(n)]
    print("imports: " + ", ".join(names))
    if bad:
        raise SystemExit(f"Keymaster.ofx imports non-system DLLs: {', '.join(bad)}")
    exports = out[out.find("[Ordinal/Name Pointer] Table"):] if "[Ordinal/Name Pointer] Table" in out else ""
    for name in ("OfxGetNumberOfPlugins", "OfxGetPlugin"):
        if name not in exports:
            raise SystemExit(f"Keymaster.ofx does not export {name}")


def build(platform: str, version: str) -> Path:
    build_dir = HERE / "build" / platform
    cmd = ["cmake", "-S", str(HERE), "-B", str(build_dir), "-DCMAKE_BUILD_TYPE=Release",
           f"-DKEYMASTER_VERSION={version}", "-DKEYMASTER_TESTS=OFF"]
    if platform == "windows" and os.name != "nt":
        cmd.append(f"-DCMAKE_TOOLCHAIN_FILE={HERE / 'cmake' / 'mingw-w64-x86_64.cmake'}")
    run(cmd)
    run(["cmake", "--build", str(build_dir), "--config", "Release", "-j", str(os.cpu_count() or 2)])
    bundle = build_dir / "Keymaster.ofx.bundle"
    binary = bundle / "Contents" / ARCH_DIRS[platform] / "Keymaster.ofx"
    if not binary.is_file():
        raise SystemExit(f"missing {binary}")
    if platform == "windows":
        check_imports(binary)
    return bundle


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--platform", choices=sorted(ARCH_DIRS), default="windows" if sys.platform == "win32" else "linux")
    args = ap.parse_args()
    bundle = build(args.platform, args.version)
    out = Path(args.out) / f"keymaster-openfx-{args.version}-{args.platform}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    legal = notices()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo.from_file(path, f"Keymaster.ofx.bundle/{path.relative_to(bundle).as_posix()}")
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, path.read_bytes())
        zf.writestr("Keymaster.ofx.bundle/Contents/Resources/THIRD_PARTY_LICENSES.txt", legal)
        installer = HERE / "install" / INSTALLERS[args.platform]
        info = zipfile.ZipInfo(installer.name)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100755 << 16
        zf.writestr(info, installer.read_bytes())
        for doc in ("README.md", "README.es-419.md"):
            zf.write(HERE / doc, doc)
        zf.write(ROOT / "LICENSE", "LICENSE")
        zf.writestr("THIRD_PARTY_LICENSES.txt", legal)
    print(out)


if __name__ == "__main__":
    main()
