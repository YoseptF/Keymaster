#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def platforms(pkg: Path) -> list[str]:
    meta = json.loads((pkg / "package.json").read_text())
    return meta.get("keymaster", {}).get("platforms", ["any"])


def jobs(only: list[str], platform: str) -> list[tuple[Path, str | None]]:
    wanted = ["linux", "windows"] if platform == "all" else [platform]
    found = sorted(p for p in (ROOT / "packages").iterdir() if (p / "build.py").is_file())
    picked: list[tuple[Path, str | None]] = []
    for pkg in found:
        if only and pkg.name not in only:
            continue
        targets = platforms(pkg)
        if "any" in targets:
            if "linux" in wanted:
                picked.append((pkg, None))
            continue
        picked.extend((pkg, p) for p in wanted if p in targets)
    return picked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", default=str(ROOT / "dist"))
    ap.add_argument("--suffix", default="")
    ap.add_argument("--platform", choices=("linux", "windows", "all"), default="windows" if sys.platform == "win32" else "linux")
    ap.add_argument("only", nargs="*")
    args = ap.parse_args()
    dist = Path(args.dist).resolve()
    dist.mkdir(parents=True, exist_ok=True)
    for pkg, platform in jobs(args.only, args.platform):
        meta = json.loads((pkg / "package.json").read_text())
        version = meta["version"] + args.suffix
        print(f"building {meta['name']} {version}" + (f" for {platform}" if platform else ""), flush=True)
        cmd = [sys.executable, str(pkg / "build.py"), "--out", str(dist), "--version", version]
        if platform:
            cmd += ["--platform", platform]
        subprocess.run(cmd, check=True)
    for path in sorted(dist.iterdir()):
        print(path.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
