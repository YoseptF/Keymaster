from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

from keymaster import settings
from keymaster.i18n import t

from .base import CoreCase


class SettingsPathTest(CoreCase):
    def test_linux_default_and_xdg(self):
        home = Path.home()
        self.assertEqual(settings.settings_path({}, "linux"), home / ".config" / "keymaster" / "settings.json")
        self.assertEqual(settings.settings_path({"XDG_CONFIG_HOME": "/x"}, "linux"), Path("/x/keymaster/settings.json"))

    def test_windows_appdata(self):
        self.assertEqual(settings.settings_path({"APPDATA": "C:/Users/a/AppData/Roaming"}, "win32"),
                         Path("C:/Users/a/AppData/Roaming") / "Keymaster" / "settings.json")

    def test_settings_env_wins(self):
        self.assertEqual(settings.settings_path({"KEYMASTER_SETTINGS": "/s.json", "XDG_CONFIG_HOME": "/x"}, "linux"),
                         Path("/s.json"))


class SettingsCommandTest(CoreCase):
    def test_defaults_when_missing(self):
        code, text = self.run_cli("settings", "get", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(text), {"language": "en"})

    def test_set_then_get(self):
        code, text = self.run_cli("settings", "set", "language", "es-419", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(text)["language"], "es-419")
        stored = json.loads(Path(os.environ["KEYMASTER_SETTINGS"]).read_text())
        self.assertEqual(stored["language"], "es-419")
        code, text = self.run_cli("settings", "get", "language", "--json")
        self.assertEqual(json.loads(text), "es-419")

    def test_set_keeps_other_keys(self):
        Path(os.environ["KEYMASTER_SETTINGS"]).write_text(json.dumps({"python": "/p", "extra": 1}))
        self.run_cli("settings", "set", "core", "/c", "--json")
        stored = json.loads(Path(os.environ["KEYMASTER_SETTINGS"]).read_text())
        self.assertEqual(stored, {"python": "/p", "extra": 1, "core": "/c"})

    def test_unknown_language_reads_as_english(self):
        Path(os.environ["KEYMASTER_SETTINGS"]).write_text(json.dumps({"language": "fr"}))
        _, text = self.run_cli("settings", "get", "language", "--json")
        self.assertEqual(json.loads(text), "en")

    def test_corrupt_file_reads_as_defaults(self):
        Path(os.environ["KEYMASTER_SETTINGS"]).write_text("{not json")
        _, text = self.run_cli("settings", "get", "--json")
        self.assertEqual(json.loads(text), {"language": "en"})

    def test_env_overrides(self):
        Path(os.environ["KEYMASTER_SETTINGS"]).write_text(json.dumps({"language": "en", "python": "/file", "core": "/filecore"}))
        with mock.patch.dict(os.environ, {"KEYMASTER_LANGUAGE": "es-419", "KEYMASTER_PYTHON": "/env", "KEYMASTER_CORE": "/envcore"}):
            _, text = self.run_cli("settings", "get", "--json")
        self.assertEqual(json.loads(text), {"language": "es-419", "python": "/env", "core": "/envcore"})

    def test_rejects_bad_values(self):
        for argv in (("language", "fr"), ("colour", "red"), ("language",)):
            code, text = self.run_cli("settings", "set", *argv, "--json")
            self.assertEqual(code, 1)
            event = json.loads(text.splitlines()[-1])
            self.assertEqual(event["message_key"], "core.error.invalid_setting")

    def test_translation_follows_language(self):
        self.assertEqual(t("core.error.cancelled", lang="en"), "Cancelled.")
        self.assertEqual(t("core.error.cancelled", lang="es-419"), "Cancelado.")
        self.assertIn("/x", t("core.error.input_unreadable", {"path": "/x"}, lang="es-419"))
        with mock.patch.dict(os.environ, {"KEYMASTER_LANGUAGE": "es-419"}):
            self.assertEqual(t("core.error.cancelled"), "Cancelado.")
