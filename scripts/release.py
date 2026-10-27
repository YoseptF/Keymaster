#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

INSTALLER = "keymaster-installer"
BUNDLE_ID = "keymaster-installer-bundles-the-packages"
BUNDLE_EN = "Bundles the updated packages."
BUNDLE_ES = "Incluye los paquetes actualizados."
SUMS = "SHA256SUMS"
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
DEFAULT_REPO = "YoseptF/Keymaster"
BUMPS = ("major", "minor", "patch")
RELEASE_LINE = re.compile(r"""^\s*["']?([^"':\s]+)["']?\s*:\s*(major|minor|patch)\s*$""")
RC_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)-rc\.(\d+)$")
RC_BANNER = ("**Release candidate.** For testing before the final release: install it and report anything that breaks.\n\n"
             "**Versión candidata.** Para probar antes de la versión final: instálala y reporta cualquier cosa que falle.")
GUARD = ("error: {cmd} publishes release files and only runs inside GitHub Actions. "
         "Release files are built by CI only, see 'Releases are built by CI only' in CONTRIBUTING.md.")
TEST_GUARD = ("error: {cmd} refused: KEYMASTER_RELEASE_TEST only allows a local origin and a stub gh "
              "(KEYMASTER_GH), but origin is {url!r}")
LOCAL_URL = re.compile(r"^(?:file://)?/")


class ReleaseError(Exception):
    pass


@dataclass
class Changeset:
    id: str
    releases: dict[str, str] = field(default_factory=dict)
    en: str = ""
    es: str = ""


def run(cmd: list[str], cwd: Path, env: dict | None = None, capture: bool = True) -> str:
    result = subprocess.run(cmd, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE if capture else sys.stderr,
                            stderr=subprocess.PIPE if capture else None)
    if result.returncode != 0:
        detail = (result.stderr or "").strip() if capture else ""
        raise ReleaseError(f"{' '.join(cmd)} failed ({result.returncode}){': ' + detail if detail else ''}")
    return result.stdout if capture else ""


def git(root: Path, *args: str) -> str:
    return run(["git", *args], root).strip()


def gh(root: Path, *args: str) -> str:
    return run([*shlex.split(os.environ.get("KEYMASTER_GH", "gh")), *args], root)


def repo_root() -> Path:
    return Path(run(["git", "rev-parse", "--show-toplevel"], Path.cwd()).strip())


def origin_url(root: Path) -> str:
    result = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def require_remote_access(root: Path, cmd: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return
    if os.environ.get("KEYMASTER_RELEASE_TEST") == "1":
        url = origin_url(root)
        if LOCAL_URL.match(url) and os.environ.get("KEYMASTER_GH"):
            return
        raise ReleaseError(TEST_GUARD.format(cmd=cmd, url=url))
    raise ReleaseError(GUARD.format(cmd=cmd))


def push(root: Path, *refs: str, env: dict | None = None) -> None:
    require_remote_access(root, "git push")
    run(["git", "push", "origin", *refs], root, env)


def gh_write(root: Path, *args: str) -> str:
    require_remote_access(root, f"gh {' '.join(args[:2])}")
    return gh(root, *args)


def repo_name() -> str:
    return os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO


def parse_changeset(cid: str, text: str) -> Changeset:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ReleaseError(f".changeset/{cid}.md does not start with a --- header")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise ReleaseError(f".changeset/{cid}.md has no closing --- line") from None
    cs = Changeset(cid)
    for line in lines[1:end]:
        if not line.strip():
            continue
        match = RELEASE_LINE.match(line)
        if not match:
            raise ReleaseError(f".changeset/{cid}.md: cannot read the release line {line!r}")
        cs.releases[match.group(1)] = match.group(2)
    english = []
    for line in lines[end + 1:]:
        line = line.strip()
        if line.startswith("es-419:"):
            cs.es = line[len("es-419:"):].strip()
        elif line:
            english.append(line)
    cs.en = " ".join(english)
    return cs


def changeset_ids(root: Path) -> list[str]:
    return sorted(p.stem for p in (root / ".changeset").glob("*.md") if p.name != "README.md")


def changeset_ids_at(root: Path, sha: str) -> list[str]:
    names = git(root, "ls-tree", "--name-only", f"{sha}:.changeset").splitlines()
    return sorted(n[:-3] for n in names if n.endswith(".md") and n != "README.md")


def read_changesets(root: Path, ids: list[str]) -> list[Changeset]:
    return [parse_changeset(cid, (root / ".changeset" / f"{cid}.md").read_text(encoding="utf-8")) for cid in ids]


def needs_bundle(changesets: list[Changeset]) -> bool:
    released = {name for cs in changesets for name in cs.releases}
    return bool(released) and INSTALLER not in released


def bundle_text() -> str:
    return f'---\n"{INSTALLER}": patch\n---\n\n{BUNDLE_EN}\nes-419: {BUNDLE_ES}\n'


def packages(root: Path) -> dict[str, dict]:
    found = {}
    for path in sorted((root / "packages").glob("*/package.json")):
        meta = json.loads(path.read_text(encoding="utf-8"))
        found[meta["name"]] = {"dir": path.parent.name, "version": meta["version"]}
    return found


def set_version(path: Path, version: str) -> None:
    text = path.read_text(encoding="utf-8")
    new, count = re.subn(r'("version"\s*:\s*")[^"]*(")', rf"\g<1>{version}\g<2>", text, count=1)
    if count != 1:
        raise ReleaseError(f"{path} has no version field")
    path.write_text(new, encoding="utf-8")


def stamp(root: Path, versions: dict[str, str]) -> None:
    known = packages(root)
    unknown = sorted(set(versions) - set(known))
    if unknown:
        raise ReleaseError(f"unknown packages: {', '.join(unknown)}")
    for name, version in versions.items():
        set_version(root / "packages" / known[name]["dir"] / "package.json", version)


def sync_lockfile(root: Path, versions: dict[str, str]) -> None:
    lock = root / "bun.lock"
    if not lock.is_file():
        return
    text = lock.read_text(encoding="utf-8")
    dirs = {name: meta["dir"] for name, meta in packages(root).items()}
    for name, version in versions.items():
        pattern = re.compile(r'("packages/' + re.escape(dirs[name]) + r'"\s*:\s*\{\s*"name"\s*:\s*"' + re.escape(name)
                             + r'"\s*,\s*"version"\s*:\s*")[^"]*(")')
        text = pattern.sub(rf"\g<1>{version}\g<2>", text, count=1)
    lock.write_text(text, encoding="utf-8")


def apply_versions(root: Path, changesets: list[Changeset]) -> tuple[list[Changeset], dict[str, dict]]:
    if needs_bundle(changesets):
        (root / ".changeset" / f"{BUNDLE_ID}.md").write_text(bundle_text(), encoding="utf-8")
        changesets = changesets + [parse_changeset(BUNDLE_ID, bundle_text())]
    before = {name: meta["version"] for name, meta in packages(root).items()}
    run([str(root / "node_modules" / ".bin" / "changeset"), "version"], root, capture=False)
    after = {name: meta["version"] for name, meta in packages(root).items()}
    sync_lockfile(root, after)
    return changesets, {name: {"old": before[name], "new": after[name]} for name in after}


def bumped(versions: dict[str, dict]) -> list[str]:
    changed = [name for name, v in versions.items() if v["old"] != v["new"]]
    return sorted(changed, key=lambda name: (name != INSTALLER, name))


def is_major(version: dict) -> bool:
    return version["old"].split(".")[0] != version["new"].split(".")[0]


def rc_number(tags: list[str], product: str) -> int:
    pattern = re.compile(r"^v" + re.escape(product) + r"-rc\.(\d+)$")
    return 1 + max((int(m.group(1)) for m in map(pattern.match, tags) if m), default=0)


def newest_rc(tags: list[str]) -> str:
    candidates = [(tuple(int(g) for g in m.groups()), tag) for tag in tags if (m := RC_TAG.match(tag))]
    if not candidates:
        raise ReleaseError("there is no release candidate tag (v<version>-rc.<n>); cut one first")
    return max(candidates)[1]


def split_rc(tag: str) -> tuple[str, int]:
    match = RC_TAG.match(tag)
    if not match:
        raise ReleaseError(f"{tag} is not a release candidate tag like v1.2.3-rc.1")
    return ".".join(match.groups()[:3]), int(match.group(4))


def tags(root: Path) -> list[str]:
    return git(root, "tag", "--list").splitlines()


def adding_commit(root: Path, cid: str, rev: str) -> str:
    out = git(root, "log", "--diff-filter=A", "--format=%H", rev, "--", f".changeset/{cid}.md").splitlines()
    return out[-1] if out else ""


def links(root: Path, changesets: list[Changeset], rev: str = "HEAD") -> dict[str, dict]:
    found = {}
    asked: dict[str, list] = {}
    for cs in changesets:
        if cs.id == BUNDLE_ID:
            continue
        sha = adding_commit(root, cs.id, rev)
        if not sha:
            continue
        if sha not in asked:
            asked[sha] = json.loads(gh(root, "api", f"repos/{repo_name()}/commits/{sha}/pulls") or "[]")
        pulls = sorted(asked[sha], key=lambda pr: (not pr.get("merged_at"), pr["number"]))
        if pulls:
            pr = pulls[0]
            found[cs.id] = {"pr": pr["number"], "url": pr["html_url"], "user": (pr.get("user") or {}).get("login", "")}
        else:
            found[cs.id] = {"commit": sha}
    return found


def entry(cs: Changeset, link: dict | None) -> str:
    ref = ""
    if link and "pr" in link:
        ref = f"[#{link['pr']}]({link['url']})"
        if link.get("user"):
            ref += f" by [@{link['user']}](https://github.com/{link['user']})"
    elif link and "commit" in link:
        ref = f"[`{link['commit'][:7]}`](https://github.com/{repo_name()}/commit/{link['commit']})"
    line = f"- {cs.en or '(no description)'}" + (f" ({ref})" if ref else "")
    if cs.es:
        line += f"  \n  es-419: {cs.es}"
    return line


def ordered(changesets: list[Changeset], found: dict[str, dict]) -> list[Changeset]:
    def key(cs: Changeset):
        link = found.get(cs.id) or {}
        return (cs.id == BUNDLE_ID, link.get("pr", float("inf")), cs.id)
    return sorted(changesets, key=key)


def notes(changesets: list[Changeset], versions: dict[str, dict], found: dict[str, dict]) -> str:
    parts = []
    for name in bumped(versions):
        v = versions[name]
        lines = [entry(cs, found.get(cs.id)) for cs in ordered(changesets, found) if name in cs.releases]
        parts.append(f"### {name} {v['old']} → {v['new']}\n\n" + "\n".join(lines))
    return "\n\n".join(parts) + "\n"


def update_changelogs(root: Path, changesets: list[Changeset], versions: dict[str, dict], found: dict[str, dict]) -> None:
    dirs = {name: meta["dir"] for name, meta in packages(root).items()}
    for name in bumped(versions):
        path = root / "packages" / dirs[name] / "CHANGELOG.md"
        title = f"# {name}\n\n"
        old = path.read_text(encoding="utf-8") if path.is_file() else title
        rest = old[len(title):] if old.startswith(title) else old
        lines = [entry(cs, found.get(cs.id)) for cs in ordered(changesets, found) if name in cs.releases]
        section = f"## {versions[name]['new']}\n\n" + "\n".join(lines) + "\n"
        path.write_text(title + section + ("\n" + rest.lstrip("\n") if rest.strip() else ""), encoding="utf-8")


def asset_parts(filename: str, versions: dict[str, str], label: str = "") -> tuple[str, str, str] | None:
    for name in sorted(versions, key=len, reverse=True):
        stem = f"{name}-{versions[name]}{label}"
        rest = filename[len(stem):]
        if filename.startswith(stem) and rest[:1] in ("-", ".") and not rest.startswith("-rc."):
            return name, versions[name], rest
    return None


def labelled(filename: str, versions: dict[str, str], rc: int) -> str:
    parts = asset_parts(filename, versions)
    if not parts:
        raise ReleaseError(f"{filename} is not a file of a package at the release versions")
    name, version, rest = parts
    return f"{name}-{version}-rc.{rc}{rest}"


def unlabelled(filename: str, versions: dict[str, str], rc: int) -> str:
    parts = next((p for name in versions if (p := asset_parts(filename, {name: versions[name]}, f"-rc.{rc}"))), None)
    if not parts:
        raise ReleaseError(f"{filename} is not a release candidate {rc} file of a package at the versions being released")
    name, version, rest = parts
    return f"{name}-{version}{rest}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def asset_files(dist: Path) -> list[Path]:
    return sorted(p for p in dist.iterdir() if p.is_file() and p.name != SUMS)


def write_sums(dist: Path) -> dict[str, str]:
    sums = {p.name: sha256(p) for p in asset_files(dist)}
    (dist / SUMS).write_text("".join(f"{h}  {n}\n" for n, h in sorted(sums.items())), encoding="utf-8")
    return sums


def read_sums(dist: Path) -> dict[str, str]:
    path = dist / SUMS
    if not path.is_file():
        raise ReleaseError(f"{SUMS} is missing from {dist}")
    sums = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(None, 1)
            sums[name.lstrip("*")] = digest
    return sums


def verify_sums(dist: Path) -> dict[str, str]:
    sums = read_sums(dist)
    present = {p.name for p in asset_files(dist)}
    if set(sums) != present:
        raise ReleaseError(f"{SUMS} lists {sorted(sums)} but the release has {sorted(present)}")
    for name, digest in sums.items():
        if sha256(dist / name) != digest:
            raise ReleaseError(f"{name} does not match its checksum in {SUMS}")
    return sums


def upload_order(dist: Path) -> list[Path]:
    files = asset_files(dist)
    installers = [p for p in files if p.name.startswith(f"{INSTALLER}-")]
    rest = [p for p in files if p not in installers]
    tail = [dist / SUMS] if (dist / SUMS).is_file() else []
    return installers + rest + tail


def check_coverage(dist: Path, versions: dict[str, str]) -> None:
    names = {asset_parts(p.name, versions)[0] for p in asset_files(dist)}
    missing = sorted(set(versions) - names)
    if missing:
        raise ReleaseError(f"the build has no files for {', '.join(missing)}")


def header(root: Path, dist: Path) -> str:
    return run(["bash", str(root / "scripts" / "installer-notes.sh"), str(dist)], root).strip()


def publish(root: Path, tag: str, title: str, body: str, dist: Path, prerelease: bool) -> None:
    handle, name = tempfile.mkstemp(prefix="keymaster-notes-", suffix=".md")
    notes_file = Path(name)
    with os.fdopen(handle, "w", encoding="utf-8") as f:
        f.write(body)
    create = ["release", "create", tag, "--verify-tag", "--draft", "--title", title, "--notes-file", str(notes_file)]
    gh_write(root, *(create + (["--prerelease"] if prerelease else [])))
    for path in upload_order(dist):
        gh_write(root, "release", "upload", tag, str(path))
    gh_write(root, "release", "edit", tag, "--draft=false", *(["--prerelease"] if prerelease else ["--latest"]))
    notes_file.unlink()
    print(f"published {title} ({tag})")


def write_output(values: dict[str, str]) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            for key, value in values.items():
                f.write(f"{key}={value}\n")


def write_summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def announce_majors(versions: dict[str, dict]) -> str:
    lines = []
    for name in bumped(versions):
        v = versions[name]
        if is_major(v):
            line = f"MAJOR release: {name} {v['old']} → {v['new']}"
            print(f"::warning title=MAJOR release::{line}")
            lines.append(f"**{line}**")
    return "\n\n".join(lines)


def cut_prepare(root: Path, out: Path) -> dict:
    ids = changeset_ids(root)
    changesets = read_changesets(root, ids)
    if not any(cs.releases for cs in changesets):
        raise ReleaseError("there are no pending changesets: nothing would change, so there is no release candidate to cut. "
                           "Merge a PR with a changeset into main first.")
    found = links(root, changesets)
    changesets, versions = apply_versions(root, changesets)
    product = versions[INSTALLER]["new"]
    existing = tags(root)
    if f"v{product}" in existing:
        raise ReleaseError(f"v{product} is already released; the pending changesets did not move the installer past it")
    rc = rc_number(existing, product)
    plan = {
        "product": product,
        "rc": rc,
        "tag": f"v{product}-rc.{rc}",
        "title": f"Keymaster {product} RC {rc}",
        "sha": git(root, "rev-parse", "HEAD"),
        "versions": {name: v["new"] for name, v in versions.items()},
        "changes": {name: versions[name] for name in bumped(versions)},
        "changesets": ids,
    }
    text = notes(changesets, versions, found)
    out.mkdir(parents=True, exist_ok=True)
    (out / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    (out / "notes.md").write_text(text, encoding="utf-8")
    majors = announce_majors(versions)
    print(f"{plan['title']}: {plan['tag']} from {plan['sha'][:7]}")
    for name in bumped(versions):
        print(f"  {name} {versions[name]['old']} → {versions[name]['new']}")
    write_output({"sha": plan["sha"], "tag": plan["tag"], "versions": json.dumps(plan["versions"], separators=(",", ":"))})
    write_summary(f"## {plan['title']}\n\n" + (majors + "\n\n" if majors else "") + text)
    return plan


def cut_publish(root: Path, plan_dir: Path, dist: Path) -> None:
    require_remote_access(root, "release.py cut-publish")
    plan = json.loads((plan_dir / "plan.json").read_text(encoding="utf-8"))
    if (dist / SUMS).exists():
        raise ReleaseError(f"{dist} already has a {SUMS}; it must hold only this run's build")
    files = asset_files(dist)
    if not files:
        raise ReleaseError(f"{dist} is empty; the build job produced nothing")
    renames = {p: dist / labelled(p.name, plan["versions"], plan["rc"]) for p in files}
    check_coverage(dist, plan["versions"])
    for src, dst in renames.items():
        src.rename(dst)
    write_sums(dist)
    body = RC_BANNER + "\n\n" + header(root, dist) + "\n\n" + (plan_dir / "notes.md").read_text(encoding="utf-8")
    git(root, "tag", plan["tag"], plan["sha"])
    push(root, f"refs/tags/{plan['tag']}")
    publish(root, plan["tag"], plan["title"], body, dist, prerelease=True)


def bot_env() -> dict:
    env = dict(os.environ)
    env.update({"GIT_AUTHOR_NAME": BOT_NAME, "GIT_AUTHOR_EMAIL": BOT_EMAIL,
                "GIT_COMMITTER_NAME": BOT_NAME, "GIT_COMMITTER_EMAIL": BOT_EMAIL})
    return env


def push_main(root: Path, branch: str) -> None:
    env = bot_env()
    require_remote_access(root, "git push")
    try:
        push(root, f"HEAD:refs/heads/{branch}", env=env)
    except ReleaseError as first:
        print(f"push rejected, rebasing on the new {branch} and retrying once: {first}")
        run(["git", "pull", "--rebase", "origin", branch], root, env)
        push(root, f"HEAD:refs/heads/{branch}", env=env)


def promote(root: Path, rc_tag: str, dist: Path, branch: str = "main") -> None:
    require_remote_access(root, "release.py promote")
    existing = tags(root)
    rc_tag = rc_tag or newest_rc(existing)
    if rc_tag not in existing:
        raise ReleaseError(f"there is no tag {rc_tag}")
    product, rc = split_rc(rc_tag)
    if f"v{product}" in existing:
        raise ReleaseError(f"v{product} is already released")
    rc_sha = git(root, "rev-list", "-n", "1", rc_tag)
    print(f"promoting {rc_tag} ({rc_sha[:7]}) to v{product}")

    dist.mkdir(parents=True, exist_ok=True)
    if any(dist.iterdir()):
        raise ReleaseError(f"{dist} must be empty")
    gh(root, "release", "download", rc_tag, "--dir", str(dist))
    rc_sums = verify_sums(dist)

    in_rc = changeset_ids_at(root, rc_sha)
    pending = changeset_ids(root)
    gone = sorted(set(in_rc) - set(pending))
    if gone:
        raise ReleaseError(f"changesets in {rc_tag} are no longer pending on {branch}: {', '.join(gone)}")
    later = {cid: (root / ".changeset" / f"{cid}.md").read_text(encoding="utf-8") for cid in pending if cid not in in_rc}
    for cid in later:
        (root / ".changeset" / f"{cid}.md").unlink()
    changesets = read_changesets(root, in_rc)
    if not any(cs.releases for cs in changesets):
        raise ReleaseError(f"{rc_tag} has no changesets that release anything")
    found = links(root, changesets)
    changesets, versions = apply_versions(root, changesets)
    for cid, text in later.items():
        (root / ".changeset" / f"{cid}.md").write_text(text, encoding="utf-8")
    if versions[INSTALLER]["new"] != product:
        raise ReleaseError(f"{rc_tag} was built as {product} but its changesets now give {INSTALLER} {versions[INSTALLER]['new']}")
    final = {name: v["new"] for name, v in versions.items()}
    renames = {p: dist / unlabelled(p.name, final, rc) for p in asset_files(dist)}
    (dist / SUMS).unlink()
    for src, dst in renames.items():
        src.rename(dst)
    check_coverage(dist, final)
    new_sums = write_sums(dist)
    if sorted(rc_sums.values()) != sorted(new_sums.values()):
        raise ReleaseError("renaming changed file contents")

    body = header(root, dist) + "\n\n" + notes(changesets, versions, found)
    update_changelogs(root, changesets, versions, found)
    env = bot_env()
    run(["git", "add", "-A", ".changeset", "packages", *(["bun.lock"] if (root / "bun.lock").is_file() else [])], root, env)
    run(["git", "commit", "-m", "Version packages"], root, env)
    push_main(root, branch)

    new_tags = [f"v{product}"] + [f"{name}@{versions[name]['new']}" for name in bumped(versions)]
    for tag in new_tags:
        git(root, "tag", tag, rc_sha)
    push(root, *[f"refs/tags/{tag}" for tag in new_tags])
    print("tagged " + ", ".join(new_tags))

    publish(root, f"v{product}", f"Keymaster {product}", body, dist, prerelease=False)

    listed = json.loads(gh(root, "release", "list", "--limit", "1000", "--json", "tagName,isPrerelease") or "[]")
    pattern = re.compile(r"^v" + re.escape(product) + r"-rc\.\d+$")
    for release in listed:
        if release.get("isPrerelease") and pattern.match(release["tagName"]):
            gh_write(root, "release", "delete", release["tagName"], "--yes")
            print(f"deleted the pre-release {release['tagName']} (its tag stays)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("cut-prepare")
    p.add_argument("--out", required=True)
    p = sub.add_parser("stamp")
    p.add_argument("versions")
    p = sub.add_parser("cut-publish")
    p.add_argument("--plan", required=True)
    p.add_argument("--dist", required=True)
    p = sub.add_parser("promote")
    p.add_argument("--rc", default="")
    p.add_argument("--dist", required=True)
    p.add_argument("--branch", default="main")
    args = ap.parse_args(argv)
    try:
        root = repo_root()
        if args.command == "cut-prepare":
            cut_prepare(root, Path(args.out).resolve())
        elif args.command == "stamp":
            stamp(root, json.loads(args.versions))
        elif args.command == "cut-publish":
            cut_publish(root, Path(args.plan).resolve(), Path(args.dist).resolve())
        elif args.command == "promote":
            promote(root, args.rc.strip(), Path(args.dist).resolve(), args.branch)
    except ReleaseError as error:
        message = str(error)
        print(message if message.startswith("error:") else f"::error::{message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
