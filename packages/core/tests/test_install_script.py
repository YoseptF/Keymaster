from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from keymaster import paths

REQUIREMENTS = "numpy>=1.26,<2\nutils3d @ git+https://github.com/EasternJournalist/utils3d.git@83bfa5b\ntqdm>=4.67"

FAKE_UV_SH = """#!/bin/sh
printf 'uv %s\\n' "$*" >> "$KM_LOG"
if [ "$1" = venv ]; then
  mkdir -p "$4/bin"
  printf '#!/bin/sh\\nprintf "python %%s\\\\n" "$*" >> "$KM_LOG"\\n' > "$4/bin/python"
  chmod +x "$4/bin/python"
fi
if [ "$1" = pip ]; then
  while [ $# -gt 0 ]; do
    if [ "$1" = -r ]; then printf 'requirements %s\\n' "$2" >> "$KM_LOG"; sed 's/^/  | /' "$2" >> "$KM_LOG"; fi
    shift
  done
fi
"""

class InstallScriptCase(unittest.TestCase):
    script = "install.sh"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="keymaster-install-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.core = self.tmp / "core"
        (self.core / "upstream").mkdir(parents=True)
        shutil.copy(paths.CORE_DIR / self.script, self.core / self.script)
        (self.core / "upstream" / "requirements.txt").write_text(REQUIREMENTS, encoding="utf-8")
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        uv = self.bin / "uv"
        uv.write_text(FAKE_UV_SH)
        uv.chmod(uv.stat().st_mode | stat.S_IEXEC)
        self.log = self.tmp / "log.txt"
        self.wheels = self.tmp / "wheels"
        self.wheels.mkdir()
        (self.wheels / "utils3d-1.7-py3-none-any.whl").write_bytes(b"wheel")

    def command(self) -> list[str]:
        return ["bash", str(self.core / self.script)]

    def run_install(self, **extra) -> str:
        env = {k: v for k, v in os.environ.items() if not k.startswith("KEYMASTER_")}
        env.update({"PATH": f"{self.bin}{os.pathsep}{env.get('PATH', '')}", "KM_LOG": str(self.log),
                    "KEYMASTER_SETTINGS": str(self.tmp / "settings.json"), "TMPDIR": str(self.tmp / "t")})
        (self.tmp / "t").mkdir(exist_ok=True)
        env.update(extra)
        proc = subprocess.run(self.command(), env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return self.log.read_text(encoding="utf-8")

    def requirement_lines(self, log: str) -> list[str]:
        return [line[4:] for line in log.splitlines() if line.startswith("  | ")]

    def test_bundled_wheel_replaces_the_git_requirement(self):
        log = self.run_install(KEYMASTER_WHEELS=str(self.wheels))
        lines = self.requirement_lines(log)
        wheel = (self.wheels / "utils3d-1.7-py3-none-any.whl").resolve()
        self.assertEqual(lines[0], "numpy>=1.26,<2")
        self.assertEqual(lines[2], "tqdm>=4.67")
        self.assertTrue(lines[1].startswith("utils3d @ file:///"), lines[1])
        self.assertTrue(lines[1].endswith(wheel.as_posix().lstrip("/")), lines[1])
        self.assertNotIn("git+", "\n".join(lines))
        self.assertEqual(list((self.tmp / "t").iterdir()), [])

    def test_without_wheels_uses_the_original_file(self):
        log = self.run_install()
        used = [line[len("requirements "):] for line in log.splitlines() if line.startswith("requirements ")]
        self.assertEqual([Path(p).resolve() for p in used], [(self.core / "upstream" / "requirements.txt").resolve()])
        self.assertIn("utils3d @ git+https://github.com/EasternJournalist/utils3d.git@83bfa5b", self.requirement_lines(log))

    def test_wheel_folder_without_a_match_keeps_git(self):
        (self.wheels / "utils3d-1.7-py3-none-any.whl").unlink()
        log = self.run_install(KEYMASTER_WHEELS=str(self.wheels))
        self.assertIn("utils3d @ git+https://github.com/EasternJournalist/utils3d.git@83bfa5b", self.requirement_lines(log))

    def test_steps_run_in_order(self):
        log = self.run_install(KEYMASTER_WHEELS=str(self.wheels))
        steps = [line for line in log.splitlines() if not line.startswith("  | ")]
        self.assertTrue(steps[0].startswith("uv venv --python 3.12 "), steps)
        self.assertIn("torch==2.9.1 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cu128", steps[1])
        self.assertTrue(steps[2].startswith("uv pip install --python "), steps)
        self.assertEqual(steps[-2:], ["python -m keymaster setup", "python -m keymaster doctor"])


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "the Linux installer needs bash")
class BashInstallScriptTest(InstallScriptCase):
    pass


del InstallScriptCase
