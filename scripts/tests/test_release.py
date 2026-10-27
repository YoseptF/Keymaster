from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import release
from tests.fixture import GH_STUB, ROOT, SCRIPTS, changeset, git, lockfile


def cs(cid: str, releases: dict[str, str], en: str = "", es: str = "") -> release.Changeset:
    return release.parse_changeset(cid, changeset(releases, en, es))


class TempDirTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="keymaster-release-unit-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)


class ParseTest(unittest.TestCase):
    def test_reads_packages_bumps_and_both_languages(self) -> None:
        text = '---\n"keymaster-core": minor\n\'keymaster-app\': patch\n---\n\nKeys footage\nwith hints.\nes-419: Hace keying.\n'
        parsed = release.parse_changeset("core", text)
        self.assertEqual(parsed.releases, {"keymaster-core": "minor", "keymaster-app": "patch"})
        self.assertEqual(parsed.en, "Keys footage with hints.")
        self.assertEqual(parsed.es, "Hace keying.")

    def test_empty_changeset(self) -> None:
        parsed = release.parse_changeset("tooling", "---\n---\n")
        self.assertEqual((parsed.releases, parsed.en, parsed.es), ({}, "", ""))

    def test_rejects_broken_files(self) -> None:
        with self.assertRaises(release.ReleaseError):
            release.parse_changeset("x", "no header\n")
        with self.assertRaises(release.ReleaseError):
            release.parse_changeset("x", '---\n"keymaster-core": huge\n---\n')
        with self.assertRaises(release.ReleaseError):
            release.parse_changeset("x", '---\n"keymaster-core": minor\n')


class BundleTest(unittest.TestCase):
    def test_installer_gets_a_patch_when_only_other_packages_bump(self) -> None:
        self.assertTrue(release.needs_bundle([cs("a", {"keymaster-core": "patch"})]))
        self.assertFalse(release.needs_bundle([cs("a", {"keymaster-core": "patch"}), cs("b", {"keymaster-installer": "patch"})]))
        self.assertFalse(release.needs_bundle([cs("a", {})]))
        self.assertFalse(release.needs_bundle([]))
        bundle = release.parse_changeset(release.BUNDLE_ID, release.bundle_text())
        self.assertEqual(bundle.releases, {"keymaster-installer": "patch"})
        self.assertEqual((bundle.en, bundle.es), ("Bundles the updated packages.", "Incluye los paquetes actualizados."))


class TagTest(unittest.TestCase):
    def test_rc_number_counts_the_candidates_of_that_version(self) -> None:
        self.assertEqual(release.rc_number([], "0.1.0"), 1)
        tags = ["v0.1.0-rc.1", "v0.1.0-rc.2", "v0.2.0-rc.5", "v0.1.0", "keymaster-core@0.1.0", "v0.1.0-rc.x", "v0.1.00-rc.9"]
        self.assertEqual(release.rc_number(tags, "0.1.0"), 3)
        self.assertEqual(release.rc_number(tags, "0.2.0"), 6)
        self.assertEqual(release.rc_number(tags, "1.0.0"), 1)

    def test_newest_rc_compares_numbers_not_text(self) -> None:
        self.assertEqual(release.newest_rc(["v0.9.0-rc.12", "v0.10.0-rc.1", "v0.10.0"]), "v0.10.0-rc.1")
        self.assertEqual(release.newest_rc(["v1.0.0-rc.9", "v1.0.0-rc.10", "keymaster-core@9.0.0"]), "v1.0.0-rc.10")
        with self.assertRaises(release.ReleaseError):
            release.newest_rc(["v1.0.0", "keymaster-core@1.0.0"])

    def test_split_rc(self) -> None:
        self.assertEqual(release.split_rc("v1.2.3-rc.4"), ("1.2.3", 4))
        with self.assertRaises(release.ReleaseError):
            release.split_rc("v1.2.3")


class AssetNameTest(unittest.TestCase):
    versions = {"keymaster-core": "0.1.0", "keymaster-installer": "1.0.0", "keymaster-openfx": "0.0.1", "keymaster-core-extra": "2.0.0"}

    def test_label_goes_after_the_version(self) -> None:
        cases = {
            "keymaster-core-0.1.0.zip": "keymaster-core-0.1.0-rc.3.zip",
            "keymaster-installer-1.0.0-windows.exe": "keymaster-installer-1.0.0-rc.3-windows.exe",
            "keymaster-installer-1.0.0-linux.sh": "keymaster-installer-1.0.0-rc.3-linux.sh",
            "keymaster-openfx-0.0.1-linux.zip": "keymaster-openfx-0.0.1-rc.3-linux.zip",
            "keymaster-core-extra-2.0.0.zip": "keymaster-core-extra-2.0.0-rc.3.zip",
        }
        for built, labelled in cases.items():
            self.assertEqual(release.labelled(built, self.versions, 3), labelled)
            self.assertEqual(release.unlabelled(labelled, self.versions, 3), built)

    def test_refuses_files_that_do_not_belong(self) -> None:
        for name in ("keymaster-core-0.0.9.zip", "notes.txt", "keymaster-core-0.1.0-rc.1.zip", "keymaster-core-0.1.0x.zip"):
            with self.assertRaises(release.ReleaseError, msg=name):
                release.labelled(name, self.versions, 1)
        with self.assertRaises(release.ReleaseError):
            release.unlabelled("keymaster-core-0.1.0-rc.2.zip", self.versions, 3)
        with self.assertRaises(release.ReleaseError):
            release.unlabelled("keymaster-core-0.1.1-rc.3.zip", self.versions, 3)


class ChecksumTest(TempDirTest):
    def test_sums_verify_and_catch_tampering(self) -> None:
        (self.tmp / "keymaster-core-0.1.0.zip").write_bytes(b"core")
        (self.tmp / "keymaster-installer-0.1.0-linux.sh").write_bytes(b"installer")
        sums = release.write_sums(self.tmp)
        text = (self.tmp / "SHA256SUMS").read_text()
        self.assertIn(f"{sums['keymaster-core-0.1.0.zip']}  keymaster-core-0.1.0.zip\n", text)
        self.assertEqual(release.verify_sums(self.tmp), sums)
        if shutil.which("sha256sum"):
            check = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=self.tmp, capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        (self.tmp / "keymaster-core-0.1.0.zip").write_bytes(b"other")
        with self.assertRaisesRegex(release.ReleaseError, "does not match"):
            release.verify_sums(self.tmp)
        release.write_sums(self.tmp)
        (self.tmp / "extra.zip").write_bytes(b"x")
        with self.assertRaisesRegex(release.ReleaseError, "lists"):
            release.verify_sums(self.tmp)
        (self.tmp / "SHA256SUMS").unlink()
        with self.assertRaisesRegex(release.ReleaseError, "missing"):
            release.verify_sums(self.tmp)

    def test_upload_order_is_installers_then_zips_then_sums(self) -> None:
        for name in ("keymaster-app-1.0.0.zip", "keymaster-installer-1.0.0-windows.exe", "SHA256SUMS",
                     "keymaster-core-1.0.0.zip", "keymaster-installer-1.0.0-linux.sh"):
            (self.tmp / name).write_text(name)
        self.assertEqual([p.name for p in release.upload_order(self.tmp)], [
            "keymaster-installer-1.0.0-linux.sh", "keymaster-installer-1.0.0-windows.exe",
            "keymaster-app-1.0.0.zip", "keymaster-core-1.0.0.zip", "SHA256SUMS"])


class NotesTest(unittest.TestCase):
    def test_grouped_by_package_installer_first_with_links_and_spanish(self) -> None:
        changesets = [
            cs("b-core", {"keymaster-core": "minor", "keymaster-app": "patch"}, "Core and app.", "Core y app."),
            cs("a-core", {"keymaster-core": "patch"}, "Core fix.", "Arreglo del core."),
            cs("installer", {"keymaster-installer": "minor"}, "One download.", "Una descarga."),
            cs("loose", {"keymaster-app": "patch"}, "From a direct push.", "Desde un push directo."),
            cs("empty", {}),
        ]
        versions = {
            "keymaster-app": {"old": "1.0.0", "new": "1.0.1"},
            "keymaster-core": {"old": "0.1.0", "new": "0.2.0"},
            "keymaster-installer": {"old": "0.1.0", "new": "0.2.0"},
            "keymaster-openfx": {"old": "0.3.0", "new": "0.3.0"},
        }
        found = {
            "b-core": {"pr": 7, "url": "https://github.com/o/r/pull/7", "user": "alice"},
            "a-core": {"pr": 9, "url": "https://github.com/o/r/pull/9", "user": "bob"},
            "installer": {"pr": 3, "url": "https://github.com/o/r/pull/3", "user": ""},
            "loose": {"commit": "0123456789abcdef"},
        }
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "o/r"}):
            text = release.notes(changesets, versions, found)
        self.assertEqual(text, "\n".join([
            "### keymaster-installer 0.1.0 → 0.2.0",
            "",
            "- One download. ([#3](https://github.com/o/r/pull/3))  ",
            "  es-419: Una descarga.",
            "",
            "### keymaster-app 1.0.0 → 1.0.1",
            "",
            "- Core and app. ([#7](https://github.com/o/r/pull/7) by [@alice](https://github.com/alice))  ",
            "  es-419: Core y app.",
            "- From a direct push. ([`0123456`](https://github.com/o/r/commit/0123456789abcdef))  ",
            "  es-419: Desde un push directo.",
            "",
            "### keymaster-core 0.1.0 → 0.2.0",
            "",
            "- Core and app. ([#7](https://github.com/o/r/pull/7) by [@alice](https://github.com/alice))  ",
            "  es-419: Core y app.",
            "- Core fix. ([#9](https://github.com/o/r/pull/9) by [@bob](https://github.com/bob))  ",
            "  es-419: Arreglo del core.",
            "",
        ]))

    def test_majors_are_announced(self) -> None:
        versions = {"keymaster-core": {"old": "1.4.0", "new": "2.0.0"}, "keymaster-app": {"old": "0.1.0", "new": "0.2.0"}}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            text = release.announce_majors(versions)
        self.assertIn("::warning title=MAJOR release::MAJOR release: keymaster-core 1.4.0 → 2.0.0", out.getvalue())
        self.assertNotIn("keymaster-app", out.getvalue())
        self.assertEqual(text, "**MAJOR release: keymaster-core 1.4.0 → 2.0.0**")


class RepoTest(TempDirTest):
    def make_repo(self) -> Path:
        repo = self.tmp / "repo"
        (repo / ".changeset").mkdir(parents=True)
        for name in ("core", "installer"):
            (repo / "packages" / name).mkdir(parents=True)
            meta = {"name": f"keymaster-{name}", "version": "0.1.0", "private": True}
            if name == "installer":
                meta["keymaster"] = {"platforms": ["linux", "windows"]}
            (repo / "packages" / name / "package.json").write_text(json.dumps(meta, indent=2).replace('[\n      "linux",\n      "windows"\n    ]', '["linux", "windows"]') + "\n")
        (repo / ".changeset" / "README.md").write_text("readme\n")
        git(repo.parent, "init", "-q", "-b", "main", str(repo))
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "init")
        return repo

    def test_changesets_at_a_commit(self) -> None:
        repo = self.make_repo()
        (repo / ".changeset" / "first.md").write_text(changeset({"keymaster-core": "patch"}, "One.", "Uno."))
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "first")
        rc = git(repo, "rev-parse", "HEAD")
        (repo / ".changeset" / "second.md").write_text(changeset({"keymaster-core": "patch"}, "Two.", "Dos."))
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "second")
        self.assertEqual(release.changeset_ids_at(repo, rc), ["first"])
        self.assertEqual(release.changeset_ids(repo), ["first", "second"])

    def test_links_find_the_pr_that_added_each_changeset(self) -> None:
        repo = self.make_repo()
        (repo / ".changeset" / "via-pr.md").write_text(changeset({"keymaster-core": "patch"}, "One.", "Uno."))
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "pr")
        pr_sha = git(repo, "rev-parse", "HEAD")
        (repo / ".changeset" / "via-pr.md").write_text(changeset({"keymaster-core": "minor"}, "One, edited.", "Uno."))
        (repo / ".changeset" / "pushed.md").write_text(changeset({"keymaster-core": "patch"}, "Two.", "Dos."))
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "push")
        push_sha = git(repo, "rev-parse", "HEAD")
        state = self.tmp / "gh"
        state.mkdir()
        (state / "pulls.json").write_text(json.dumps({pr_sha: [{"number": 12, "html_url": "https://x/pull/12", "user": {"login": "ana"}}]}))
        env = {"KEYMASTER_GH": f"{sys.executable} {GH_STUB}", "GH_STUB_DIR": str(state), "GITHUB_REPOSITORY": "o/r"}
        with mock.patch.dict(os.environ, env):
            found = release.links(repo, release.read_changesets(repo, ["pushed", "via-pr"]) + [cs(release.BUNDLE_ID, {})])
        self.assertEqual(found, {"via-pr": {"pr": 12, "url": "https://x/pull/12", "user": "ana"}, "pushed": {"commit": push_sha}})
        calls = [json.loads(line) for line in (state / "calls.jsonl").read_text().splitlines()]
        self.assertEqual(calls, [["api", f"repos/o/r/commits/{push_sha}/pulls"], ["api", f"repos/o/r/commits/{pr_sha}/pulls"]])

    def test_stamp_keeps_the_file_layout(self) -> None:
        repo = self.make_repo()
        before = (repo / "packages" / "installer" / "package.json").read_text()
        release.stamp(repo, {"keymaster-installer": "2.0.0"})
        after = (repo / "packages" / "installer" / "package.json").read_text()
        self.assertEqual(after, before.replace('"version": "0.1.0"', '"version": "2.0.0"'))
        self.assertIn('["linux", "windows"]', after)
        with self.assertRaises(release.ReleaseError):
            release.stamp(repo, {"keymaster-nope": "1.0.0"})

    def test_lockfile_follows_the_new_versions(self) -> None:
        repo = self.make_repo()
        (repo / "bun.lock").write_text(lockfile({"core": "0.1.0", "installer": "0.1.0"}))
        release.sync_lockfile(repo, {"keymaster-core": "0.2.0", "keymaster-installer": "0.1.0"})
        text = (repo / "bun.lock").read_text()
        self.assertIn('"packages/core": {\n      "name": "keymaster-core",\n      "version": "0.2.0",', text)
        self.assertIn('"packages/installer": {\n      "name": "keymaster-installer",\n      "version": "0.1.0",', text)

    def test_real_lockfile_layout_is_understood(self) -> None:
        repo = self.make_repo()
        real = (ROOT / "bun.lock").read_text()
        (repo / "bun.lock").write_text(real)
        release.sync_lockfile(repo, {"keymaster-core": "9.9.9"})
        changed = (repo / "bun.lock").read_text()
        self.assertNotEqual(changed, real)
        self.assertIn('"name": "keymaster-core",\n      "version": "9.9.9"', changed)

    def test_changelog_sections_go_on_top(self) -> None:
        repo = self.make_repo()
        versions = {"keymaster-core": {"old": "0.1.0", "new": "0.2.0"}, "keymaster-installer": {"old": "0.1.0", "new": "0.1.0"}}
        found = {"one": {"pr": 1, "url": "https://x/pull/1", "user": "ana"}}
        release.update_changelogs(repo, [cs("one", {"keymaster-core": "minor"}, "New.", "Nuevo.")], versions, found)
        versions = {"keymaster-core": {"old": "0.2.0", "new": "0.2.1"}, "keymaster-installer": {"old": "0.1.0", "new": "0.1.0"}}
        release.update_changelogs(repo, [cs("two", {"keymaster-core": "patch"}, "Fix.", "Arreglo.")], versions, {})
        self.assertEqual((repo / "packages" / "core" / "CHANGELOG.md").read_text(), "\n".join([
            "# keymaster-core", "", "## 0.2.1", "", "- Fix.  ", "  es-419: Arreglo.", "",
            "## 0.2.0", "", "- New. ([#1](https://x/pull/1) by [@ana](https://github.com/ana))  ", "  es-419: Nuevo.", ""]))
        self.assertFalse((repo / "packages" / "installer" / "CHANGELOG.md").exists())


class GuardTest(unittest.TestCase):
    def test_publishing_commands_refuse_outside_actions(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"}
        for args in (["cut-publish", "--plan", "p", "--dist", "d"], ["promote", "--dist", "d"]):
            err = io.StringIO()
            with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stderr(err), \
                    mock.patch.object(release, "gh", side_effect=AssertionError("gh called")), \
                    mock.patch.object(release, "git", side_effect=AssertionError("git called")):
                self.assertEqual(release.main(args), 1)
            self.assertIn("only runs inside GitHub Actions", err.getvalue())
            self.assertIn("'Releases are built by CI only' in CONTRIBUTING.md", err.getvalue())
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises(release.ReleaseError):
                release.require_actions("x")
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            release.require_actions("x")


class InstallerNotesTest(TempDirTest):
    def notes(self) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(SCRIPTS / "installer-notes.sh"), str(self.tmp)], capture_output=True, text=True)

    def test_bilingual_header_names_the_installers(self) -> None:
        for name in ("keymaster-installer-1.0.0-rc.2-linux.sh", "keymaster-installer-1.0.0-rc.2-windows.exe", "keymaster-core-1.0.0-rc.2.zip"):
            (self.tmp / name).write_text("x")
        result = self.notes()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("**Install Keymaster:** download `keymaster-installer-1.0.0-rc.2-windows.exe` (Windows) "
                                                 "or `keymaster-installer-1.0.0-rc.2-linux.sh` (Linux) and run it."), result.stdout)
        self.assertIn("**Instalar Keymaster:** descarga `keymaster-installer-1.0.0-rc.2-windows.exe` (Windows) o "
                      "`keymaster-installer-1.0.0-rc.2-linux.sh` (Linux) y ejecútalo.", result.stdout)
        self.assertIn("are for advanced users", result.stdout)
        self.assertIn("son para usuarios avanzados", result.stdout)

    def test_fails_without_both_installers(self) -> None:
        (self.tmp / "keymaster-installer-1.0.0-linux.sh").write_text("x")
        result = self.notes()
        self.assertEqual(result.returncode, 1)
        self.assertIn("needs both the Windows and the Linux installer", result.stderr)


if __name__ == "__main__":
    unittest.main()
