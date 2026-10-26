#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / "keymaster"
MANIFEST = "blender_manifest.toml"
LANGS = ("en", "es-419")
VERSION_LINE = re.compile(r'^version\s*=\s*"[^"]*"\s*$', re.MULTILINE)


def manifest(version: str) -> str:
    text = (SOURCE / MANIFEST).read_text(encoding="utf-8")
    if not VERSION_LINE.search(text):
        raise SystemExit(f"{MANIFEST} has no version line")
    return VERSION_LINE.sub(f'version = "{version}"', text, count=1)


def sources():
    for path in sorted(SOURCE.rglob("*")):
        rel = path.relative_to(SOURCE)
        if not path.is_file() or "__pycache__" in rel.parts or path.suffix == ".pyc" or rel.as_posix() == MANIFEST:
            continue
        yield path, rel.as_posix()


def build(out_dir: Path, version: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"keymaster-blender-{version}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST, manifest(version))
        for path, name in sources():
            zf.write(path, name)
        for lang in LANGS:
            zf.write(HERE / "i18n" / f"{lang}.json", f"i18n/{lang}.json")
            zf.write(ROOT / "packages" / "core" / "i18n" / f"{lang}.json", f"i18n/core/{lang}.json")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--version", required=True)
    args = ap.parse_args()
    print(build(Path(args.out), args.version))


if __name__ == "__main__":
    main()
