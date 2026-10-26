from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest

from tests.helpers import APP, FAKE_CORE, TempEnv

PINNED = "6.12.0"


def pyside_version() -> str | None:
    try:
        import PySide6
    except ImportError:
        return None
    return PySide6.__version__


@unittest.skipIf(sys.platform == "win32" or not shutil.which("bash"), "the Linux installer needs bash")
class InstallScriptTest(TempEnv):
    def run_install(self, **extra: str) -> subprocess.CompletedProcess:
        env = {k: v for k, v in os.environ.items() if not k.startswith("KEYMASTER_")}
        env.update({
            "HOME": str(self.tmp / "home"),
            "XDG_CONFIG_HOME": str(self.tmp / "cfg"),
            "XDG_DATA_HOME": str(self.tmp / "data"),
            "XDG_BIN_HOME": str(self.tmp / "bin"),
            "LANG": "C",
        })
        env.update(extra)
        return subprocess.run(["bash", str(APP / "install.sh")], env=env, capture_output=True, text=True, timeout=120)

    def write_settings(self, **values: str) -> None:
        path = self.tmp / "cfg" / "keymaster" / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(values, indent=2), encoding="utf-8")

    def test_refuses_without_core(self) -> None:
        result = self.run_install()
        self.assertEqual(result.returncode, 1)
        self.assertIn("isn't installed yet", result.stderr)
        self.assertIn(str(self.tmp / "cfg" / "keymaster" / "settings.json"), result.stderr)
        self.assertFalse((self.tmp / "bin" / "keymaster-app").exists())

    def test_refusal_is_translated(self) -> None:
        result = self.run_install(KEYMASTER_LANGUAGE="es-419")
        self.assertEqual(result.returncode, 1)
        self.assertIn("todavía no está instalado", result.stderr)

    def test_bad_python(self) -> None:
        self.write_settings(language="en", python=str(self.tmp / "missing" / "python"), core=str(FAKE_CORE))
        result = self.run_install()
        self.assertEqual(result.returncode, 1)
        self.assertIn(str(self.tmp / "missing" / "python"), result.stderr)

    @unittest.skipUnless(pyside_version() == PINNED, "needs the pinned PySide6 already installed to stay offline")
    def test_installs_launcher_and_menu_entry(self) -> None:
        self.write_settings(language="es-419", python=sys.executable, core=str(FAKE_CORE))
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        launcher = self.tmp / "bin" / "keymaster-app"
        self.assertTrue(os.access(launcher, os.X_OK))
        script = launcher.read_text()
        self.assertIn(str(APP), script)
        self.assertIn(sys.executable, script)
        desktop = (self.tmp / "data" / "applications" / "keymaster-app.desktop").read_text(encoding="utf-8")
        self.assertIn(f'Exec="{launcher}" %F', desktop)
        self.assertIn("Comment[es_419]=Recorta clips", desktop)
        self.assertTrue((self.tmp / "data" / "icons" / "hicolor" / "scalable" / "apps" / "keymaster-app.svg").is_file())
        self.assertIn("Listo.", result.stdout)
        probe = subprocess.run(["sh", "-c", f'PYTHONPATH="{APP}" "{sys.executable}" -c "import keymaster_app.app"'],
                               capture_output=True, text=True)
        self.assertEqual(probe.returncode, 0, probe.stderr)


if __name__ == "__main__":
    unittest.main()
