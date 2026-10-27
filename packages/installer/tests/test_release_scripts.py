from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import helpers

SCRIPTS = helpers.ROOT / "scripts"
FAKE_GH = """#!/bin/sh
if [ "$1 $2" = "release view" ]; then exit 1; fi
printf '%s\\n' "---" >> "$GH_LOG"
for arg in "$@"; do printf '%s\\n' "$arg" >> "$GH_LOG"; done
"""


def load_check():
    spec = importlib.util.spec_from_file_location("check_i18n", SCRIPTS / "check-i18n.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(shutil.which("bash") and shutil.which("jq") and shutil.which("git"), "needs bash, jq and git")
class ReleaseScriptsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="keymaster-release-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        helpers.executable(self.bin / "gh", FAKE_GH)
        self.log = self.tmp / "gh.log"
        self.repo = self.tmp / "repo"
        dist = self.repo / "dist"
        dist.mkdir(parents=True)
        for name in ("keymaster-app-0.2.0.zip", "keymaster-core-0.3.0.zip", "keymaster-installer-0.1.0-linux.sh",
                     "keymaster-installer-0.1.0-windows.exe", "keymaster-openfx-0.1.0-windows.zip"):
            (dist / name).write_text("x")
        for name, version in (("core", "0.3.0"), ("installer", "0.1.0")):
            pkg = self.repo / "packages" / name
            pkg.mkdir(parents=True)
            (pkg / "package.json").write_text(json.dumps({"name": f"keymaster-{name}", "version": version}))
            (pkg / "CHANGELOG.md").write_text(f"# keymaster-{name}\n\n## {version}\n\n- Something new for {name}.\n")
        git = ["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run(git + ["init", "-q"], check=True)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-qm", "init"], check=True)
        subprocess.run(git + ["tag", "keymaster-core@0.3.0"], check=True)
        subprocess.run(git + ["tag", "keymaster-installer@0.1.0"], check=True)

    def run_script(self, name: str, actions: bool = True) -> subprocess.CompletedProcess:
        env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_ACTIONS", "GITHUB_REPOSITORY")}
        env.update({"PATH": f"{self.bin}{os.pathsep}{env['PATH']}", "GH_LOG": str(self.log), "GITHUB_SHA": "abcdef1234567",
                    "GITHUB_REPOSITORY": "owner/repo"})
        if actions:
            env["GITHUB_ACTIONS"] = "true"
        return subprocess.run(["bash", str(SCRIPTS / name)], cwd=self.repo, env=env, capture_output=True, text=True, timeout=60)

    def calls(self) -> list[list[str]]:
        chunks = self.log.read_text(encoding="utf-8").split("---\n")[1:] if self.log.exists() else []
        return [chunk.rstrip("\n").split("\n") for chunk in chunks]

    def test_refuse_to_publish_outside_actions(self) -> None:
        for name in ("staging-release.sh", "github-releases.sh"):
            result = self.run_script(name, actions=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("only runs inside GitHub Actions", result.stderr)
            self.assertIn("CONTRIBUTING.md", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_staging_lists_the_installers_first(self) -> None:
        result = self.run_script("staging-release.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        create = next(call for call in self.calls() if call[:2] == ["release", "create"])
        notes = create[create.index("--notes") + 1:]
        text = "\n".join(notes)
        self.assertTrue(text.startswith("**Install Keymaster:** download `keymaster-installer-0.1.0-windows.exe` (Windows) or "
                                        "`keymaster-installer-0.1.0-linux.sh` (Linux)"), text)
        self.assertIn("**Instalar Keymaster:** descarga `keymaster-installer-0.1.0-windows.exe` (Windows) o", text)
        self.assertIn("are for advanced users", text)
        self.assertIn("son para usuarios avanzados", text)
        files = [arg for arg in create if arg.startswith("dist/")]
        self.assertEqual(files[:2], ["dist/keymaster-installer-0.1.0-linux.sh", "dist/keymaster-installer-0.1.0-windows.exe"])
        self.assertEqual(len(files), 5)

    def test_production_releases_point_at_the_installer(self) -> None:
        result = self.run_script("github-releases.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        releases = {call[2]: call for call in self.calls() if call[:2] == ["release", "create"]}
        self.assertEqual(set(releases), {"keymaster-core@0.3.0", "keymaster-installer@0.1.0"})
        core = "\n".join(releases["keymaster-core@0.3.0"])
        self.assertIn("from the [installer release](https://github.com/owner/repo/releases/tag/keymaster-installer%400.1.0)", core)
        self.assertIn("- Something new for core.", core)
        self.assertIn("dist/keymaster-core-0.3.0.zip", releases["keymaster-core@0.3.0"])
        installer = releases["keymaster-installer@0.1.0"]
        self.assertTrue(installer[installer.index("--notes") + 1].startswith("**Install Keymaster:** download `keymaster-installer-0.1.0-windows.exe`"))
        self.assertNotIn("installer release](", "\n".join(installer))
        self.assertEqual([a for a in installer if a.startswith("dist/")],
                         ["dist/keymaster-installer-0.1.0-linux.sh", "dist/keymaster-installer-0.1.0-windows.exe"])


class NsisLanguageCheckTest(unittest.TestCase):
    def test_nsis_key_uses_and_hardcoded_text(self) -> None:
        check = load_check()
        self.assertIn(".nsi", check.CODE_SUFFIXES)
        text = "\n".join([
            'DetailPrint "Copying files"',
            'MessageBox MB_OK "Hello there"',
            'Section "Core files" S1',
            'Section "!Required" S2',
            'SectionSetText ${S1} "Other text"',
            '!define MUI_WELCOMEPAGE_TITLE "Welcome"',
            'DetailPrint "$(installer.step.files)"',
            'Section "!$(installer.component.core)" SecCore',
            'Section "-hidden"',
            'Section "Uninstall"',
            'MessageBox MB_OK "$1"',
        ])
        flagged = [m.group(0).strip() for pattern in check.HARDCODED[".nsi"] for m in pattern.finditer(text)]
        self.assertEqual(len(flagged), 6, flagged)
        used = {key for pattern in check.KEY_USES for key in pattern.findall(text)}
        self.assertEqual(used, {"installer.step.files", "installer.component.core"})
