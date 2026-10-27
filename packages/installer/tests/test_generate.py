from __future__ import annotations

import io
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

import generate
from tests import helpers

NSIS_LINE = re.compile(r'^LangString (\S+) \$\{(LANG_\w+)\} "(.*)"$')
NSIS_LANG = {"LANG_ENGLISH": "en", "LANG_SPANISHINTERNATIONAL": "es-419"}
TRICKY = {
    "en": {"installer.a": 'Cost $5 "quoted" it\'s\nnew line {path}', "installer.b": "plain"},
    "es-419": {"installer.a": "Cuesta $$ «año» 'sí'\n\tfin {path}", "installer.b": "simple"},
}


def nsis_unescape(text: str) -> str:
    out, i = [], 0
    while i < len(text):
        if text.startswith("$$", i):
            out.append("$"); i += 2
        elif text.startswith('$\\"', i):
            out.append('"'); i += 3
        elif text.startswith("$\\r", i):
            out.append("\r"); i += 3
        elif text.startswith("$\\n", i):
            out.append("\n"); i += 3
        elif text.startswith("$\\t", i):
            out.append("\t"); i += 3
        else:
            out.append(text[i]); i += 1
    return "".join(out).replace("\r\n", "\n")


def parse_nsis(text: str) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {"en": {}, "es-419": {}}
    for line in text.splitlines():
        match = NSIS_LINE.match(line)
        assert match, line
        found[NSIS_LANG[match.group(2)]][match.group(1)] = nsis_unescape(match.group(3))
    return found


def parse_bash(include: str) -> dict[str, dict[str, str]]:
    script = include + 'for k in "${!KM_TEXT[@]}"; do printf "%s\\0%s\\0" "$k" "${KM_TEXT[$k]}"; done\n'
    raw = subprocess.run(["bash", "-c", script], capture_output=True, check=True).stdout.decode("utf-8").split("\0")[:-1]
    found: dict[str, dict[str, str]] = {"en": {}, "es-419": {}}
    for key, value in zip(raw[::2], raw[1::2]):
        lang, name = key.split(":", 1)
        found[lang][name] = value
    return found


class GeneratorTest(unittest.TestCase):
    def test_nsis_round_trips_every_key_in_both_languages(self) -> None:
        tables = generate.load_tables()
        self.assertEqual(parse_nsis(generate.nsis_langstrings(tables)), tables)

    def test_nsis_escaping(self) -> None:
        text = generate.nsis_langstrings(TRICKY)
        self.assertIn('LangString installer.a ${LANG_ENGLISH} "Cost $$5 $\\"quoted$\\" it\'s$\\r$\\nnew line {path}"', text)
        self.assertEqual(parse_nsis(text), TRICKY)

    def test_bash_round_trips_every_key_in_both_languages(self) -> None:
        tables = generate.load_tables()
        self.assertEqual(parse_bash(generate.bash_messages(tables)), tables)
        self.assertEqual(parse_bash(generate.bash_messages(TRICKY)), TRICKY)

    def test_defines_and_vars(self) -> None:
        self.assertEqual(generate.nsis_defines({"A": 'x "y" $z'}), '!define A "x $\\"y$\\" $$z"\n')
        out = subprocess.run(["bash", "-c", generate.bash_vars({"A": "it's $HOME"}) + 'printf %s "$A"'],
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(out, "it's $HOME")

    def test_scripts_only_use_defined_keys(self) -> None:
        keys = set(generate.load_tables()["en"])
        nsi = (helpers.PACKAGE / "windows" / "keymaster.nsi").read_text(encoding="utf-8")
        sh = (helpers.PACKAGE / "linux" / "installer.sh").read_text(encoding="utf-8")
        used = set(re.findall(r"\$\((installer\.[a-z0-9_.]+)\)", nsi)) | set(re.findall(r"""\b(?:say|msg)\s+"(installer\.[a-z0-9_.]+)\"""", sh))
        self.assertEqual(used - keys, set())
        self.assertEqual(keys - used, set())


class BuildTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="keymaster-installer-build-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.downloads = helpers.fake_downloads(self.tmp / "downloads")
        self.prebuilt = helpers.prebuilt_dir(self.tmp / "prebuilt")
        self.pins = helpers.test_pins(self.tmp, self.downloads)

    def test_linux_installer_is_one_file_with_the_payload(self) -> None:
        target = helpers.build(self.tmp / "dist", "linux", self.prebuilt, self.pins, self.tmp / "cache")
        data = target.read_bytes()
        self.assertTrue(data.startswith(b"#!/usr/bin/env bash\n"))
        self.assertTrue(target.stat().st_mode & 0o111)
        head, payload = data.split(b"\n__KEYMASTER_PAYLOAD__\n", 1)
        self.assertIn(f"KM_VERSION='{helpers.TEST_VERSION}'".encode(), head)
        with tarfile.open(fileobj=io.BytesIO(payload)) as tar:
            names = set(tar.getnames())
            install_sh = tar.getmember("core/install.sh")
        for name in ("core/keymaster/cli.py", "core/upstream/requirements.txt", "app/install.sh", "app/i18n/core/es-419.json",
                     "blender/keymaster-blender.zip", "openfx/Keymaster.ofx.bundle/Contents/Linux-x86-64/Keymaster.ofx",
                     "wheels/utils3d-1.7-py3-none-any.whl"):
            self.assertIn(name, names)
        self.assertFalse(any(n.startswith("adobe") for n in names))
        self.assertTrue(install_sh.mode & 0o100)

    def test_embedded_packages_get_the_same_suffix(self) -> None:
        out = subprocess.run(["python3", str(helpers.PACKAGE / "build.py"), "--out", str(self.tmp / "d"), "--version", "0.0.0-pr7",
                              "--platform", "linux", "--prebuilt", str(self.prebuilt), "--pins", str(self.pins), "--cache", str(self.tmp / "c")],
                             capture_output=True, text=True, check=True).stdout
        self.assertRegex(out, r"keymaster-core-\d+\.\d+\.\d+-pr7\.zip")

    def test_requirement_pin_must_match(self) -> None:
        bad = self.pins.read_text().replace("83bfa5bda008803f6521ce9547f94023b8afeddd", "1111111111111111111111111111111111111111", 1)
        self.pins.write_text(bad)
        result = subprocess.run(["python3", str(helpers.PACKAGE / "build.py"), "--out", str(self.tmp / "d"), "--version", "1",
                                 "--prebuilt", str(self.prebuilt), "--pins", str(self.pins), "--cache", str(self.tmp / "c")],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("update packages/installer/pins.json", result.stderr)

    @unittest.skipUnless(shutil.which("makensis"), "makensis is not installed")
    def test_windows_installer_builds(self) -> None:
        target = helpers.build(self.tmp / "dist", "windows", self.prebuilt, self.pins, self.tmp / "cache")
        self.assertTrue(target.is_file())
        self.assertEqual(target.read_bytes()[:2], b"MZ")
