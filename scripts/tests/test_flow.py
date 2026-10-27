from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.fixture import BOT, CHANGESET_BIN, REPO, WORKFLOWS, Fixture, changeset


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(CHANGESET_BIN.exists() and shutil.which("git") and shutil.which("bash"),
                     "needs git, bash and node_modules (run bun install)")
class ReleaseFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="keymaster-flow-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.fx = Fixture(self.tmp)

    def test_workflows_run_the_commands_this_dry_run_runs(self) -> None:
        cut = (WORKFLOWS / "release-candidate.yml").read_text()
        self.assertIn("python scripts/release.py cut-prepare --out tmp/release-plan", cut)
        self.assertIn("path: tmp/release-plan/", cut)
        self.assertIn("versions: ${{ needs.prepare.outputs.versions }}", cut)
        self.assertIn("ref: ${{ needs.prepare.outputs.sha }}", cut)
        self.assertIn("python scripts/release.py cut-publish --plan tmp/release-plan --dist tmp/release-dist", cut)
        build = (WORKFLOWS / "build.yml").read_text()
        self.assertIn('python scripts/release.py stamp "$VERSIONS"', build)
        self.assertIn("python scripts/package.py --platform all", build)
        promote = (WORKFLOWS / "promote-release.yml").read_text()
        self.assertIn("ref: main", promote)
        self.assertIn('python scripts/release.py promote --rc "$RC" --dist tmp/promote-dist', promote)
        for path in WORKFLOWS.glob("*.yml"):
            if path.name == "local-ci-off.yml":
                continue
            for line in path.read_text().splitlines():
                if line.strip().startswith("runs-on:"):
                    self.assertEqual(line.strip(), "runs-on: ${{ vars.CI_RUNNER || 'ubuntu-latest' }}", path.name)

    def test_cut_without_changesets_fails(self) -> None:
        result, _ = self.fx.cut()
        self.assertEqual(result.returncode, 1)
        self.assertIn("there are no pending changesets", result.stderr)
        self.assertEqual(self.fx.calls(), [])
        self.assertEqual(self.fx.origin_git("tag", "--list"), "")

    def test_cut_with_only_empty_changesets_fails(self) -> None:
        self.fx.merge_pr(1, "alice", {"tooling": changeset({})})
        result, _ = self.fx.cut()
        self.assertEqual(result.returncode, 1)
        self.assertIn("there are no pending changesets", result.stderr)

    def test_publishing_refuses_to_run_outside_actions(self) -> None:
        self.fx.merge_pr(1, "alice", {"core": changeset({"keymaster-core": "minor"}, "New.", "Nuevo.")})
        job = self.fx.checkout("main")
        for args in (["cut-publish", "--plan", "tmp/plan", "--dist", "tmp/dist"], ["promote", "--dist", "tmp/dist"]):
            result = self.fx.release_py(job, *args, actions=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("only runs inside GitHub Actions", result.stderr)
            self.assertIn("CONTRIBUTING.md", result.stderr)
        subprocess.run(["git", "-C", str(job), "remote", "set-url", "origin", "https://github.com/keymaster-guard-test/none.git"], check=True)
        for args in (["cut-publish", "--plan", "tmp/plan", "--dist", "tmp/dist"], ["promote", "--dist", "tmp/dist"]):
            result = self.fx.release_py(job, *args)
            self.assertEqual(result.returncode, 1)
            self.assertIn("KEYMASTER_RELEASE_TEST only allows a local origin", result.stderr)
        self.assertEqual(self.fx.calls(), [])
        self.assertEqual(self.fx.origin_git("tag", "--list"), "")

    def test_cut_twice_then_promote_the_newest(self) -> None:
        fx = self.fx
        pr1 = fx.merge_pr(1, "alice", {
            "core-keys": changeset({"keymaster-core": "minor"}, "The core keys real footage.", "El core hace keying de material real."),
            "one-click": changeset({"keymaster-installer": "minor"}, "One download installs everything.", "Una descarga instala todo."),
        })

        result, plan1 = fx.cut()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(plan1["tag"], "v0.1.0-rc.1")
        self.assertEqual(plan1["sha"], pr1)
        self.assertEqual(fx.origin_git("rev-list", "-n", "1", "v0.1.0-rc.1"), pr1)
        rc1 = fx.release("v0.1.0-rc.1")
        self.assertEqual(rc1["title"], "Keymaster 0.1.0 RC 1")
        self.assertTrue(rc1["prerelease"])
        self.assertFalse(rc1["draft"])
        self.assertEqual(rc1["assets"], [
            "keymaster-installer-0.1.0-rc.1-linux.sh",
            "keymaster-installer-0.1.0-rc.1-windows.exe",
            "keymaster-app-0.0.0-rc.1.zip",
            "keymaster-core-0.1.0-rc.1.zip",
            "keymaster-openfx-0.0.0-rc.1-linux.zip",
            "keymaster-openfx-0.0.0-rc.1-windows.zip",
            "SHA256SUMS",
        ])
        self.assertEqual(fx.asset("v0.1.0-rc.1", "keymaster-core-0.1.0-rc.1.zip").read_text(),
                         "keymaster-core version=0.1.0 platform=any\n")
        self.assertEqual(fx.asset("v0.1.0-rc.1", "keymaster-installer-0.1.0-rc.1-windows.exe").read_text(),
                         "keymaster-installer version=0.1.0 platform=windows\n")
        sums = fx.asset("v0.1.0-rc.1", "SHA256SUMS").read_text()
        self.assertIn(f"{digest(fx.asset('v0.1.0-rc.1', 'keymaster-core-0.1.0-rc.1.zip'))}  keymaster-core-0.1.0-rc.1.zip", sums)
        notes = rc1["notes"]
        self.assertTrue(notes.startswith("**Release candidate.**"), notes)
        self.assertIn("**Versión candidata.**", notes)
        self.assertIn("download `keymaster-installer-0.1.0-rc.1-windows.exe` (Windows) or `keymaster-installer-0.1.0-rc.1-linux.sh` (Linux)", notes)
        self.assertIn("descarga `keymaster-installer-0.1.0-rc.1-windows.exe` (Windows) o", notes)
        self.assertLess(notes.index("### keymaster-installer 0.0.0 → 0.1.0"), notes.index("### keymaster-core 0.0.0 → 0.1.0"))
        self.assertIn(f"- The core keys real footage. ([#1](https://github.com/{REPO}/pull/1) by [@alice](https://github.com/alice))  \n"
                      "  es-419: El core hace keying de material real.", notes)
        self.assertNotIn("keymaster-app 0.0.0", notes)
        self.assertNotIn("Bundles the updated packages.", notes)
        self.assertIsNotNone(fx.main_file(".changeset/core-keys.md"))
        self.assertEqual(fx.main_file("packages/core/package.json").count('"version": "0.0.0"'), 1)
        create = next(c for c in fx.calls() if c[:2] == ["release", "create"])
        self.assertIn("--draft", create)
        self.assertIn("--verify-tag", create)

        pr2 = fx.merge_pr(2, "bob", {
            "core-fix": changeset({"keymaster-core": "patch"}, "Fixes a crash on short clips.", "Corrige un cierre con clips cortos."),
            "tooling": changeset({}),
        })
        result, plan2 = fx.cut()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(plan2["tag"], "v0.1.0-rc.2")
        self.assertEqual(fx.origin_git("rev-list", "-n", "1", "v0.1.0-rc.2"), pr2)
        rc2 = fx.release("v0.1.0-rc.2")
        self.assertEqual(rc2["title"], "Keymaster 0.1.0 RC 2")
        self.assertIn("[#2](https://github.com/owner/repo/pull/2) by [@bob]", rc2["notes"])
        self.assertIn("keymaster-core-0.1.0-rc.2.zip", rc2["assets"])
        rc2_digests = {name.replace("-rc.2", ""): digest(fx.asset("v0.1.0-rc.2", name)) for name in rc2["assets"] if name != "SHA256SUMS"}

        fx.merge_pr(3, "carol", {"app-queue": changeset({"keymaster-app": "minor"}, "The app has a queue.", "La app tiene una cola.")})
        moved = {}

        def main_moves() -> None:
            moved["sha"] = fx.merge_pr(4, "dave", {"openfx-fix": changeset({"keymaster-openfx": "patch"}, "OpenFX fix.", "Arreglo de OpenFX.")})

        result = fx.promote(before_push=main_moves)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("push rejected, rebasing", result.stdout)

        self.assertEqual(fx.origin_git("log", "-1", "--format=%s|%an", "main"), f"Version packages|{BOT}")
        self.assertEqual(fx.origin_git("rev-parse", "main~1"), moved["sha"])
        self.assertIn('"version": "0.1.0"', fx.main_file("packages/core/package.json"))
        self.assertIn('"version": "0.1.0"', fx.main_file("packages/installer/package.json"))
        self.assertIn('"version": "0.0.0"', fx.main_file("packages/app/package.json"))
        self.assertIn('"version": "0.0.0"', fx.main_file("packages/openfx/package.json"))
        for gone in ("core-keys", "one-click", "core-fix", "tooling", "keymaster-installer-bundles-the-packages"):
            self.assertIsNone(fx.main_file(f".changeset/{gone}.md"), gone)
        for kept in ("app-queue", "openfx-fix"):
            self.assertIsNotNone(fx.main_file(f".changeset/{kept}.md"), kept)
        lock = fx.main_file("bun.lock")
        self.assertIn('"packages/core": {\n      "name": "keymaster-core",\n      "version": "0.1.0"', lock)
        self.assertIn('"packages/app": {\n      "name": "keymaster-app",\n      "version": "0.0.0"', lock)
        core_log = fx.main_file("packages/core/CHANGELOG.md")
        self.assertTrue(core_log.startswith("# keymaster-core\n\n## 0.1.0\n\n- The core keys real footage."), core_log)
        self.assertIn("- Fixes a crash on short clips. ([#2]", core_log)
        self.assertIn("  es-419: Corrige un cierre con clips cortos.", core_log)
        self.assertIsNone(fx.main_file("packages/app/CHANGELOG.md"))

        for tag in ("v0.1.0", "keymaster-core@0.1.0", "keymaster-installer@0.1.0"):
            self.assertEqual(fx.origin_git("rev-list", "-n", "1", tag), pr2, tag)
        all_tags = fx.origin_git("tag", "--list").splitlines()
        self.assertNotIn("keymaster-app@0.0.0", all_tags)
        self.assertNotIn("keymaster-openfx@0.0.0", all_tags)
        self.assertIn("v0.1.0-rc.1", all_tags)
        self.assertIn("v0.1.0-rc.2", all_tags)

        final = fx.release("v0.1.0")
        self.assertEqual(final["title"], "Keymaster 0.1.0")
        self.assertFalse(final["prerelease"])
        self.assertFalse(final["draft"])
        self.assertTrue(final["latest"])
        self.assertEqual(final["assets"], [
            "keymaster-installer-0.1.0-linux.sh",
            "keymaster-installer-0.1.0-windows.exe",
            "keymaster-app-0.0.0.zip",
            "keymaster-core-0.1.0.zip",
            "keymaster-openfx-0.0.0-linux.zip",
            "keymaster-openfx-0.0.0-windows.zip",
            "SHA256SUMS",
        ])
        self.assertEqual({name: digest(fx.asset("v0.1.0", name)) for name in final["assets"] if name != "SHA256SUMS"}, rc2_digests)
        sums = fx.asset("v0.1.0", "SHA256SUMS").read_text()
        self.assertIn(f"{rc2_digests['keymaster-core-0.1.0.zip']}  keymaster-core-0.1.0.zip", sums)
        self.assertNotIn("rc.", sums)
        self.assertTrue(final["notes"].startswith("**Install Keymaster:** download `keymaster-installer-0.1.0-windows.exe`"), final["notes"])
        self.assertIn("### keymaster-core 0.0.0 → 0.1.0", final["notes"])
        self.assertIn("[#1](https://github.com/owner/repo/pull/1) by [@alice]", final["notes"])
        self.assertIn("[#2](https://github.com/owner/repo/pull/2) by [@bob]", final["notes"])
        self.assertNotIn("The app has a queue.", final["notes"])
        self.assertNotIn("OpenFX fix.", final["notes"])
        self.assertIsNone(fx.release("v0.1.0-rc.1"))
        self.assertIsNone(fx.release("v0.1.0-rc.2"))
        deletes = [c for c in fx.calls() if c[:2] == ["release", "delete"]]
        self.assertEqual(sorted(c[2] for c in deletes), ["v0.1.0-rc.1", "v0.1.0-rc.2"])
        self.assertTrue(all("--cleanup-tag" not in c for c in deletes))

        again = fx.promote()
        self.assertEqual(again.returncode, 1)
        self.assertIn("already released", again.stderr)

        result, plan3 = fx.cut()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(plan3["tag"], "v0.1.1-rc.1")
        notes = fx.release("v0.1.1-rc.1")["notes"]
        self.assertIn("### keymaster-installer 0.1.0 → 0.1.1\n\n- Bundles the updated packages.  \n  es-419: Incluye los paquetes actualizados.", notes)
        self.assertIn("### keymaster-app 0.0.0 → 0.1.0", notes)
        self.assertIn("### keymaster-openfx 0.0.0 → 0.0.1", notes)
        self.assertIn("[#3](https://github.com/owner/repo/pull/3) by [@carol]", notes)
        self.assertIsNone(fx.main_file(".changeset/keymaster-installer-bundles-the-packages.md"))

    def test_promote_a_named_older_candidate(self) -> None:
        fx = self.fx
        pr1 = fx.merge_pr(1, "alice", {"core": changeset({"keymaster-core": "patch"}, "Fix.", "Arreglo.")})
        self.assertEqual(fx.cut()[0].returncode, 0)
        fx.merge_pr(2, "bob", {"app": changeset({"keymaster-app": "minor"}, "App.", "App.")})
        self.assertEqual(fx.cut()[0].returncode, 0)
        result = fx.promote("v0.0.1-rc.1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(fx.origin_git("rev-list", "-n", "1", "v0.0.1"), pr1)
        self.assertIsNotNone(fx.main_file(".changeset/app.md"))
        self.assertIn('"version": "0.0.0"', fx.main_file("packages/app/package.json"))
        self.assertIn('"version": "0.0.1"', fx.main_file("packages/installer/package.json"))
        self.assertIn("Bundles the updated packages.", fx.main_file("packages/installer/CHANGELOG.md"))
        self.assertEqual(fx.release("v0.0.1")["assets"][0], "keymaster-installer-0.0.1-linux.sh")

    def test_promote_refuses_a_tampered_candidate(self) -> None:
        fx = self.fx
        fx.merge_pr(1, "alice", {"core": changeset({"keymaster-core": "patch"}, "Fix.", "Arreglo.")})
        self.assertEqual(fx.cut()[0].returncode, 0)
        fx.asset("v0.0.1-rc.1", "keymaster-core-0.0.1-rc.1.zip").write_text("swapped\n")
        result = fx.promote()
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match its checksum", result.stderr)
        self.assertEqual(fx.origin_git("log", "-1", "--format=%s", "main"), "Change number 1")
        self.assertIsNone(fx.release("v0.0.1"))


if __name__ == "__main__":
    unittest.main()
