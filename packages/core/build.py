#!/usr/bin/env python3
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SKIP_DIRS = {"__pycache__", "tests", ".venv", "venv", "node_modules"}
SKIP_PREFIXES = (("upstream", "weights"), ("upstream", "vfms"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--version", required=True)
    args = ap.parse_args()
    out = Path(args.out) / f"keymaster-core-{args.version}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(HERE.rglob("*")):
            rel = path.relative_to(HERE)
            if not path.is_file() or SKIP_DIRS & set(rel.parts[:-1]) or path.suffix == ".pyc" or rel.parts[:2] in SKIP_PREFIXES:
                continue
            if rel.parts[0] in {"build.py", "package.json", "CHANGELOG.md"}:
                continue
            zf.write(path, f"keymaster-core/{rel.as_posix()}")
        for keep in ("upstream/weights", "upstream/vfms/cradio", "upstream/vfms/moge", "upstream/vfms/rvm"):
            zf.writestr(f"keymaster-core/{keep}/.gitkeep", "")
        zf.write(ROOT / "LICENSE", "keymaster-core/LICENSE")
    print(out)


if __name__ == "__main__":
    main()
