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

    def env(self, **extra):
        return {"KEYMASTER_SETTINGS": str(self.path), "LANG": "en_US.UTF-8", **extra}

    def test_missing_file(self):
        r = settings.resolve(self.env(), "linux")
        self.assertEqual((r.python, r.core, r.language, r.path), (None, None, "en", self.path))

    def test_paths_from_file_and_env(self):
        self.path.write_text(json.dumps({"python": "/py", "core": "/core"}))
        r = settings.resolve(self.env(), "linux")
        self.assertEqual((r.python, r.core), ("/py", "/core"))
        r = settings.resolve(self.env(KEYMASTER_PYTHON="/py2", KEYMASTER_CORE="/core2"), "linux")
        self.assertEqual((r.python, r.core), ("/py2", "/core2"))

    def test_language_order(self):
        def lang(file_value=None, env_value=None, locale=None, os_lang="en_US.UTF-8"):
            if file_value is None:
                self.path.write_text("{}")
            else:
                self.path.write_text(json.dumps({"language": file_value}))
            extra = {"LANG": os_lang}
            if env_value is not None:
                extra["KEYMASTER_LANGUAGE"] = env_value
            return settings.resolve(self.env(**extra), "linux", locale=locale).language

        self.assertEqual(lang(file_value="en", env_value="es-419", locale="en_US"), "es-419")
        self.assertEqual(lang(file_value="en", locale="es"), "en")
        self.assertEqual(lang(file_value="es-419", locale="en_US"), "es-419")
        self.assertEqual(lang(file_value="auto", locale="es"), "es-419")
        self.assertEqual(lang(locale="es"), "es-419")
        self.assertEqual(lang(file_value="fr", locale="es"), "es-419")
        self.assertEqual(lang(env_value="auto", file_value="auto", locale="en_US", os_lang="es_MX.UTF-8"), "en")
        self.assertEqual(lang(os_lang="es_MX.UTF-8"), "es-419")
        self.assertEqual(lang(os_lang="de_DE.UTF-8"), "en")
        self.assertEqual(lang(locale="fr_FR"), "en")

    def test_never_writes(self):
        self.path.write_text(json.dumps({"language": "auto"}))
        before = self.path.read_text()
        settings.resolve(self.env(), "linux", locale="es")
        settings.configured_language(self.env(), "linux")
        self.assertEqual(self.path.read_text(), before)

    def test_garbage_file(self):
        self.path.write_text("not json")
        self.assertIsNone(settings.configured_language(self.env(), "linux"))
        self.path.write_text("[]")
        self.assertEqual(settings.read(self.path), {})


class Locales(unittest.TestCase):
    def test_language_from_locale(self):
        for name in ("es", "es_MX", "es_ES.UTF-8", "es-419", "Spanish_Mexico", "ES"):
            self.assertEqual(settings.language_from_locale(name), "es-419", name)
        for name in (None, "", "en_US", "en_GB", "fr_FR", "C", "eo", "pt_BR"):
            self.assertEqual(settings.language_from_locale(name), "en", name)

    def test_os_locale_env_order(self):
        env = {"LC_ALL": "", "LC_MESSAGES": "es_AR.UTF-8", "LANG": "en_US.UTF-8"}
        self.assertEqual(settings.os_locale(env, "linux"), "es_AR.UTF-8")
        self.assertEqual(settings.os_locale({"LC_ALL": "C", "LANG": "es_CO"}, "linux"), "es_CO")
        self.assertEqual(settings.os_locale({"LANGUAGE": "es_MX:en"}, "linux"), "es_MX")
        self.assertEqual(settings.os_locale({"LC_ALL": "fr_FR"}, "linux"), "fr_FR")


if __name__ == "__main__":
    unittest.main()
