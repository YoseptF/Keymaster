#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXTENSION = HERE / "extension"
BUNDLE = "com.keymaster.adobe"
TOP = "keymaster-adobe"
LANGS = ("en", "es-419")


def manifest_version(version: str) -> str:
    match = re.match(r"\d+(?:\.\d+){0,2}", version)
    if not match:
        raise SystemExit(f"version {version!r} does not start with a number")
    parts = match.group(0).split(".")
    return ".".join(parts + ["0"] * (3 - len(parts)))


def manifest(version: str) -> str:
    text = (EXTENSION / "CSXS" / "manifest.xml").read_text(encoding="utf-8")
    numeric = manifest_version(version)
    text, bundle = re.subn(r'ExtensionBundleVersion="[^"]*"', f'ExtensionBundleVersion="{numeric}"', text)
    text, ext = re.subn(r'(<Extension Id="[^"]+" )Version="[^"]*"', rf'\g<1>Version="{numeric}"', text)
    if bundle != 1 or ext != 1:
        raise SystemExit("manifest.xml version attributes not found")
    return text


def write(zf: zipfile.ZipFile, arcname: str, data: bytes) -> None:
    info = zipfile.ZipInfo(arcname, date_time=(2020, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    zf.writestr(info, data)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--version", required=True)
    args = ap.parse_args()
    out = Path(args.out) / f"keymaster-adobe-{args.version}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    ext_root = f"{TOP}/{BUNDLE}"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(EXTENSION.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(EXTENSION).as_posix()
            data = manifest(args.version).encode("utf-8") if rel == "CSXS/manifest.xml" else path.read_bytes()
            write(zf, f"{ext_root}/{rel}", data)
        for lang in LANGS:
            write(zf, f"{ext_root}/i18n/adobe/{lang}.json", (HERE / "i18n" / f"{lang}.json").read_bytes())
            core_table = ROOT / "packages" / "core" / "i18n" / f"{lang}.json"
            write(zf, f"{ext_root}/i18n/core/{lang}.json", core_table.read_bytes() if core_table.is_file() else b"{}\n")
        for script in sorted((HERE / "install").iterdir()):
            write(zf, f"{TOP}/{script.name}", script.read_bytes())
        for doc in ("README.md", "README.es-419.md"):
            write(zf, f"{TOP}/{doc}", (HERE / doc).read_bytes())
        write(zf, f"{TOP}/LICENSE", (ROOT / "LICENSE").read_bytes())
    print(out)


if __name__ == "__main__":
    main()
