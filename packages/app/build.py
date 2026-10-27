#!/usr/bin/env python3
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CORE_I18N = ROOT / "packages" / "core" / "i18n"
LANGS = ("en", "es-419")
TOP_FILES = ("install.sh", "install.ps1", "README.md", "README.es-419.md")
EXECUTABLE = {"install.sh"}


def add(zf: zipfile.ZipFile, path: Path, name: str) -> None:
    info = zipfile.ZipInfo.from_file(path, name)
    mode = 0o755 if path.name in EXECUTABLE else 0o644
    info.external_attr = (0o100000 | mode) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(info, path.read_bytes())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--version", required=True)
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"keymaster-app-{args.version}.zip"
    prefix = "keymaster-app"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted((HERE / "keymaster_app").rglob("*")):
            rel = path.relative_to(HERE)
            if path.is_file() and "__pycache__" not in rel.parts and path.suffix != ".pyc":
                add(zf, path, f"{prefix}/{rel.as_posix()}")
        for lang in LANGS:
            add(zf, HERE / "i18n" / f"{lang}.json", f"{prefix}/i18n/{lang}.json")
            core_table = CORE_I18N / f"{lang}.json"
            if core_table.is_file():
                add(zf, core_table, f"{prefix}/i18n/core/{lang}.json")
        for name in TOP_FILES:
            add(zf, HERE / name, f"{prefix}/{name}")
        add(zf, ROOT / "LICENSE", f"{prefix}/LICENSE")
    print(out)


if __name__ == "__main__":
    main()
