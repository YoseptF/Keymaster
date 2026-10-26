import json
import subprocess
import sys
import tomllib
import unittest
import zipfile
from pathlib import Path

from tests.helpers import PACKAGE, ROOT, scratch


class Build(unittest.TestCase):
    def test_extension_zip(self):
        with scratch() as tmp:
            subprocess.run([sys.executable, str(PACKAGE / "build.py"), "--out", tmp, "--version", "1.2.3-pr7"],
                           check=True, capture_output=True)
            files = list(Path(tmp).iterdir())
            self.assertEqual([f.name for f in files], ["keymaster-blender-1.2.3-pr7.zip"])
            with zipfile.ZipFile(files[0]) as zf:
                names = set(zf.namelist())
                manifest = tomllib.loads(zf.read("blender_manifest.toml").decode())
                core_en = json.loads(zf.read("i18n/core/en.json"))
                host_es = json.loads(zf.read("i18n/es-419.json"))
        self.assertEqual((manifest["id"], manifest["version"], manifest["type"]), ("keymaster", "1.2.3-pr7", "add-on"))
        self.assertNotIn("platforms", manifest)
        self.assertTrue({"__init__.py", "ui.py", "i18n.py", "settings.py", "runner.py", "events.py",
                         "placement.py", "i18n/en.json", "i18n/core/es-419.json"} <= names)
        self.assertFalse([n for n in names if "__pycache__" in n or n.endswith(".pyc") or n.startswith("tests")])
        self.assertEqual(core_en, json.loads((ROOT / "packages/core/i18n/en.json").read_text(encoding="utf-8")))
        self.assertEqual(host_es["blender.cancel.label"], "Cancelar")

    def test_package_json(self):
        meta = json.loads((PACKAGE / "package.json").read_text())
        self.assertEqual(meta, {"name": "keymaster-blender", "version": "0.0.0", "private": True})


if __name__ == "__main__":
    unittest.main()
