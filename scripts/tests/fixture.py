from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
WORKFLOWS = ROOT / ".github" / "workflows"
GH_STUB = Path(__file__).with_name("gh_stub.py")
CHANGESET_BIN = ROOT / "node_modules" / ".bin" / "changeset"
REPO = "owner/repo"
PACKAGES = {"app": None, "core": None, "installer": ["linux", "windows"], "openfx": ["linux", "windows"]}
FAKE_BUILD = """import argparse
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--version", required=True)
ap.add_argument("--platform")
args = ap.parse_args()
name = json.loads((Path(__file__).resolve().parent / "package.json").read_text())["name"]
ext = {"linux": ".sh", "windows": ".exe"}.get(args.platform, ".zip") if name == "keymaster-installer" else ".zip"
tail = f"-{args.platform}{ext}" if args.platform else ext
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
(out / f"{name}-{args.version}{tail}").write_text(f"{name} version={args.version} platform={args.platform or 'any'}\\n")
"""
BOT = "github-actions[bot]"


def git(cwd: Path, *args: str) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME="Dev", GIT_AUTHOR_EMAIL="dev@example.com",
               GIT_COMMITTER_NAME="Dev", GIT_COMMITTER_EMAIL="dev@example.com")
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()


def changeset(releases: dict[str, str], en: str = "", es: str = "") -> str:
    head = "".join(f'"{name}": {bump}\n' for name, bump in releases.items())
    body = f"\n{en}\n" + (f"es-419: {es}\n" if es else "") if en else ""
    return f"---\n{head}---\n{body}"


def lockfile(versions: dict[str, str]) -> str:
    parts = ['{\n  "lockfileVersion": 1,\n  "workspaces": {\n    "": {\n      "name": "keymaster",\n    },\n']
    for name, version in versions.items():
        parts.append(f'    "packages/{name}": {{\n      "name": "keymaster-{name}",\n      "version": "{version}",\n    }},\n')
    parts.append('  },\n  "packages": {}\n}\n')
    return "".join(parts)


class Fixture:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.origin = tmp / "origin.git"
        self.dev = tmp / "dev"
        self.state = tmp / "gh"
        self.artifacts = tmp / "artifacts"
        self.jobs = 0
        self.pulls: dict[str, list] = {}
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)], check=True)
        self.dev.mkdir()
        git(self.dev, "init", "-q", "-b", "main")
        git(self.dev, "remote", "add", "origin", str(self.origin))
        self.write_tree()
        git(self.dev, "add", "-A")
        git(self.dev, "commit", "-qm", "Start the monorepo")
        git(self.dev, "push", "-q", "origin", "main")

    def write_tree(self) -> None:
        d = self.dev
        (d / "package.json").write_text(json.dumps({"name": "keymaster", "private": True, "workspaces": ["packages/*"]}, indent=2) + "\n")
        (d / "bun.lock").write_text(lockfile({name: "0.0.0" for name in PACKAGES}))
        (d / ".gitignore").write_text("node_modules\ntmp/\ndist/\n")
        (d / ".changeset").mkdir()
        shutil.copy(ROOT / ".changeset" / "config.json", d / ".changeset" / "config.json")
        (d / ".changeset" / "README.md").write_text("# Changesets\n")
        (d / "scripts").mkdir()
        for script in ("release.py", "installer-notes.sh", "package.py"):
            shutil.copy(SCRIPTS / script, d / "scripts" / script)
        for name, platforms in PACKAGES.items():
            pkg = d / "packages" / name
            pkg.mkdir(parents=True)
            meta = {"name": f"keymaster-{name}", "version": "0.0.0", "private": True}
            if platforms:
                meta["keymaster"] = {"platforms": platforms}
            (pkg / "package.json").write_text(json.dumps(meta, indent=2) + "\n")
            (pkg / "build.py").write_text(FAKE_BUILD)

    def merge_pr(self, number: int, user: str, changesets: dict[str, str]) -> str:
        git(self.dev, "pull", "-q", "--rebase", "origin", "main")
        for cid, text in changesets.items():
            (self.dev / ".changeset" / f"{cid}.md").write_text(text)
        (self.dev / "packages" / "core" / f"change-{number}.txt").write_text(f"change {number}\n")
        git(self.dev, "add", "-A")
        git(self.dev, "commit", "-qm", f"Change number {number}")
        sha = git(self.dev, "rev-parse", "HEAD")
        git(self.dev, "push", "-q", "origin", "main")
        self.pulls[sha] = [{"number": number, "html_url": f"https://github.com/{REPO}/pull/{number}", "user": {"login": user}}]
        self.state.mkdir(exist_ok=True)
        (self.state / "pulls.json").write_text(json.dumps(self.pulls))
        return sha

    def checkout(self, ref: str) -> Path:
        self.jobs += 1
        job = self.tmp / "jobs" / f"{self.jobs:02d}"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(job)], check=True)
        git(job, "checkout", "-q", ref)
        (job / "node_modules").symlink_to(ROOT / "node_modules")
        return job

    def env(self, actions: bool = True, output: Path | None = None) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("GITHUB_", "GH_", "KEYMASTER_", "GIT_"))}
        env.update({"KEYMASTER_GH": f"{sys.executable} {GH_STUB}", "GH_STUB_DIR": str(self.state),
                    "GH_STUB_REMOTE": str(self.origin), "GITHUB_REPOSITORY": REPO, "PYTHONDONTWRITEBYTECODE": "1"})
        env["GIT_ALLOW_PROTOCOL"] = "file"
        if actions:
            env["KEYMASTER_RELEASE_TEST"] = "1"
        if output:
            env["GITHUB_OUTPUT"] = str(output)
        return env

    def release_py(self, job: Path, *args: str, actions: bool = True, output: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "scripts/release.py", *args], cwd=job, env=self.env(actions, output),
                              capture_output=True, text=True, timeout=120)

    def cut(self, ref: str = "main") -> tuple[subprocess.CompletedProcess, dict]:
        prepare = self.checkout(ref)
        output = prepare / "tmp" / "github-output"
        output.parent.mkdir(parents=True)
        result = self.release_py(prepare, "cut-prepare", "--out", "tmp/release-plan", output=output)
        if result.returncode != 0:
            return result, {}
        outputs = dict(line.split("=", 1) for line in output.read_text().splitlines())
        run = self.artifacts / f"run-{self.jobs:02d}"
        shutil.copytree(prepare / "tmp" / "release-plan", run / "release-plan")
        build = self.checkout(outputs["sha"])
        stamped = self.release_py(build, "stamp", outputs["versions"])
        assert stamped.returncode == 0, stamped.stderr
        subprocess.run([sys.executable, "scripts/package.py", "--dist", str(run / "dist"), "--platform", "all"],
                       cwd=build, check=True, capture_output=True, env=self.env())
        publish = self.checkout(outputs["sha"])
        shutil.copytree(run / "dist", publish / "tmp" / "release-dist")
        shutil.copytree(run / "release-plan", publish / "tmp" / "release-plan")
        result = self.release_py(publish, "cut-publish", "--plan", "tmp/release-plan", "--dist", "tmp/release-dist")
        return result, json.loads((run / "release-plan" / "plan.json").read_text())

    def promote(self, rc: str = "", before_push=None) -> subprocess.CompletedProcess:
        job = self.checkout("main")
        if before_push:
            before_push()
        return self.release_py(job, "promote", "--rc", rc, "--dist", "tmp/promote-dist")

    def calls(self) -> list[list[str]]:
        path = self.state / "calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.is_file() else []

    def release(self, tag: str) -> dict | None:
        path = self.state / "releases" / tag / "meta.json"
        return json.loads(path.read_text()) if path.is_file() else None

    def asset(self, tag: str, name: str) -> Path:
        return self.state / "releases" / tag / "assets" / name

    def origin_git(self, *args: str) -> str:
        return subprocess.run(["git", "--git-dir", str(self.origin), *args], check=True, capture_output=True, text=True).stdout.strip()

    def main_file(self, path: str) -> str | None:
        result = subprocess.run(["git", "--git-dir", str(self.origin), "show", f"main:{path}"], capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else None
