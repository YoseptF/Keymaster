#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

STATE = Path(os.environ["GH_STUB_DIR"])
RELEASES = STATE / "releases"


def fail(message: str) -> None:
    print(f"gh stub: {message}", file=sys.stderr)
    sys.exit(1)


def flag(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args else None


def meta_path(tag: str) -> Path:
    return RELEASES / tag / "meta.json"


def load(tag: str) -> dict:
    path = meta_path(tag)
    if not path.is_file():
        fail(f"release not found: {tag}")
    return json.loads(path.read_text(encoding="utf-8"))


def save(tag: str, meta: dict) -> None:
    meta_path(tag).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def remote_has_tag(tag: str) -> bool:
    remote = os.environ.get("GH_STUB_REMOTE")
    if not remote:
        return True
    return subprocess.run(["git", "--git-dir", remote, "rev-parse", "-q", "--verify", f"refs/tags/{tag}"],
                          capture_output=True).returncode == 0


def release(args: list[str]) -> None:
    action, rest = args[0], args[1:]
    if action == "create":
        tag = rest[0]
        if "--verify-tag" in rest and not remote_has_tag(tag):
            fail(f"tag {tag} does not exist in the remote")
        if meta_path(tag).exists():
            fail(f"release {tag} already exists")
        (RELEASES / tag / "assets").mkdir(parents=True)
        notes = Path(flag(rest, "--notes-file")).read_text(encoding="utf-8")
        save(tag, {"tag": tag, "title": flag(rest, "--title"), "notes": notes, "draft": "--draft" in rest,
                   "prerelease": "--prerelease" in rest, "latest": False, "assets": []})
    elif action == "upload":
        tag, files = rest[0], rest[1:]
        meta = load(tag)
        for name in files:
            shutil.copy(name, RELEASES / tag / "assets" / Path(name).name)
            meta["assets"].append(Path(name).name)
        save(tag, meta)
    elif action == "edit":
        tag = rest[0]
        meta = load(tag)
        if "--draft=false" in rest:
            meta["draft"] = False
        if "--prerelease" in rest:
            meta["prerelease"] = True
        if "--latest" in rest:
            meta["latest"] = True
        save(tag, meta)
    elif action == "download":
        tag = rest[0]
        meta = load(tag)
        out = Path(flag(rest, "--dir"))
        out.mkdir(parents=True, exist_ok=True)
        for name in meta["assets"]:
            shutil.copy(RELEASES / tag / "assets" / name, out / name)
    elif action == "list":
        found = []
        if RELEASES.is_dir():
            for path in sorted(RELEASES.glob("*/meta.json")):
                meta = json.loads(path.read_text(encoding="utf-8"))
                found.append({"tagName": meta["tag"], "isPrerelease": meta["prerelease"]})
        print(json.dumps(found))
    elif action == "delete":
        tag = rest[0]
        load(tag)
        shutil.rmtree(RELEASES / tag)
    else:
        fail(f"unsupported: release {action}")


def api(args: list[str]) -> None:
    match = re.fullmatch(r"repos/[^/]+/[^/]+/commits/([0-9a-f]+)/pulls", args[0])
    if not match:
        fail(f"unsupported api call {args[0]}")
    pulls_file = STATE / "pulls.json"
    pulls = json.loads(pulls_file.read_text(encoding="utf-8")) if pulls_file.is_file() else {}
    print(json.dumps(pulls.get(match.group(1), [])))


def main() -> None:
    args = sys.argv[1:]
    STATE.mkdir(parents=True, exist_ok=True)
    with open(STATE / "calls.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(args) + "\n")
    if args[:1] == ["release"]:
        release(args[1:])
    elif args[:1] == ["api"]:
        api(args[1:])
    else:
        fail(f"unsupported: {' '.join(args)}")


if __name__ == "__main__":
    main()
