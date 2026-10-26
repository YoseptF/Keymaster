import json
import unittest
from pathlib import Path

from keymaster import settings
from tests.helpers import scratch


class Paths(unittest.TestCase):
    def test_linux_default(self):
        self.assertEqual(settings.settings_path({"XDG_CONFIG_HOME": "/cfg"}, "linux"),
                         Path("/cfg/keymaster/settings.json"))

    def test_linux_without_xdg(self):
        self.assertEqual(settings.settings_path({}, "linux"), Path.home() / ".config" / "keymaster" / "settings.json")

    def test_windows(self):
        self.assertEqual(settings.settings_path({"APPDATA": "C:/Users/a/AppData/Roaming"}, "win32"),
                         Path("C:/Users/a/AppData/Roaming") / "Keymaster" / "settings.json")

    def test_override(self):
        self.assertEqual(settings.settings_path({"KEYMASTER_SETTINGS": "/x/s.json", "XDG_CONFIG_HOME": "/cfg"}, "linux"),
                         Path("/x/s.json"))


class Resolve(unittest.TestCase):
    def setUp(self):
        self.tmp = scratch()
        self.path = Path(self.tmp.name) / "settings.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_file(self):
        r = settings.resolve({"KEYMASTER_SETTINGS": str(self.path)})
        self.assertEqual((r.python, r.core, r.language, r.path), (None, None, "en", self.path))

    def test_file_values(self):
        self.path.write_text(json.dumps({"python": "/py", "core": "/core", "language": "es-419"}))
        r = settings.resolve({"KEYMASTER_SETTINGS": str(self.path)})
        self.assertEqual((r.python, r.core, r.language), ("/py", "/core", "es-419"))

    def test_env_wins(self):
        self.path.write_text(json.dumps({"python": "/py", "core": "/core", "language": "es-419"}))
        r = settings.resolve({"KEYMASTER_SETTINGS": str(self.path), "KEYMASTER_PYTHON": "/py2",
                              "KEYMASTER_CORE": "/core2", "KEYMASTER_LANGUAGE": "en"})
        self.assertEqual((r.python, r.core, r.language), ("/py2", "/core2", "en"))

    def test_unknown_language_and_garbage(self):
        self.path.write_text(json.dumps({"language": "fr"}))
        self.assertEqual(settings.resolve({"KEYMASTER_SETTINGS": str(self.path)}).language, "en")
        self.path.write_text("not json")
        self.assertEqual(settings.resolve({"KEYMASTER_SETTINGS": str(self.path)}).language, "en")
        self.path.write_text("[]")
        self.assertEqual(settings.read(self.path), {})

    def test_set_language_keeps_other_keys(self):
        self.path.write_text(json.dumps({"python": "/py", "core": "/core"}))
        env = {"KEYMASTER_SETTINGS": str(self.path)}
        settings.set_language("es-419", env)
        self.assertEqual(json.loads(self.path.read_text()), {"python": "/py", "core": "/core", "language": "es-419"})
        self.assertEqual(settings.file_language(env), "es-419")
        settings.set_language("xx", env)
        self.assertEqual(settings.file_language(env), "en")
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["settings.json"])

    def test_set_language_creates_folders(self):
        nested = Path(self.tmp.name) / "a" / "b" / "settings.json"
        settings.set_language("es-419", {"KEYMASTER_SETTINGS": str(nested)})
        self.assertEqual(json.loads(nested.read_text()), {"language": "es-419"})


if __name__ == "__main__":
    unittest.main()
