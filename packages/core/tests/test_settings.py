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


class LanguageResolutionTest(CoreCase):
    def test_order(self):
        resolve = settings.resolve_language
        self.assertEqual(resolve(None, {"LANG": "es_AR.UTF-8"}, "linux"), "es-419")
        self.assertEqual(resolve(None, {"LANG": "de_DE.UTF-8"}, "linux"), "en")
        self.assertEqual(resolve(None, {}, "linux"), "en")
        self.assertEqual(resolve(None, {"LANG": "C.UTF-8"}, "linux"), "en")
        self.assertEqual(resolve(None, {"LANG": "en_US", "LC_MESSAGES": "es_ES"}, "linux"), "es-419")
        self.assertEqual(resolve(None, {"LC_ALL": "en_GB", "LC_MESSAGES": "es_ES"}, "linux"), "en")
        self.assertEqual(resolve("en", {"LANG": "es_MX"}, "linux"), "en")
        self.assertEqual(resolve("auto", {"LANG": "es_MX"}, "linux"), "es-419")
        self.assertEqual(resolve("en", {"KEYMASTER_LANGUAGE": "es-419"}, "linux"), "es-419")
        self.assertEqual(resolve("es-419", {"KEYMASTER_LANGUAGE": "es_CO"}, "linux"), "es-419")
        self.assertEqual(resolve("es-419", {"KEYMASTER_LANGUAGE": "en"}, "linux"), "en")
        self.assertEqual(resolve("es-419", {"KEYMASTER_LANGUAGE": "auto", "LANG": "en_US"}, "linux"), "es-419")

    def test_windows_uses_ui_language(self):
        with mock.patch.object(settings, "windows_ui_locale", return_value="es_MX"):
            self.assertEqual(settings.resolve_language(None, {"LANG": "en_US"}, "win32"), "es-419")
        with mock.patch.object(settings, "windows_ui_locale", return_value="en_US"):
            self.assertEqual(settings.resolve_language(None, {}, "win32"), "en")


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

    def test_unknown_or_auto_language_follows_the_os(self):
        for stored in ("fr", "auto", None):
            Path(os.environ["KEYMASTER_SETTINGS"]).write_text(json.dumps({"language": stored} if stored else {}))
            _, text = self.run_cli("settings", "get", "language", "--json")
            self.assertEqual(json.loads(text), "en")
            with mock.patch.dict(os.environ, {"LANG": "es_MX.UTF-8"}):
                _, text = self.run_cli("settings", "get", "language", "--json")
            self.assertEqual(json.loads(text), "es-419")

    def test_set_auto(self):
        code, text = self.run_cli("settings", "set", "language", "auto", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(text)["language"], "auto")

    def test_corrupt_file_reads_as_defaults(self):
        Path(os.environ["KEYMASTER_SETTINGS"]).write_text("{not json")
        _, text = self.run_cli("settings", "get", "--json")
        self.assertEqual(json.loads(text), {"language": "en"})

    def test_env_overrides(self):
        Path(os.environ["KEYMASTER_SETTINGS"]).write_text(json.dumps({"language": "en", "python": "/file", "core": "/filecore"}))
        with mock.patch.dict(os.environ, {"KEYMASTER_LANGUAGE": "es-419", "KEYMASTER_PYTHON": "/env",
                                          "KEYMASTER_CORE": "/envcore", "LANG": "en_US"}):
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


class FfmpegSettingTest(CoreCase):
    def make_ffmpeg(self) -> Path:
        tool = self.tmp / "bundled" / "bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        tool.parent.mkdir(parents=True)
        tool.write_text("")
        return tool

    def test_set_ffmpeg_is_stored(self):
        code, text = self.run_cli("settings", "set", "ffmpeg", "/opt/ff/ffmpeg", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(text)["ffmpeg"], "/opt/ff/ffmpeg")

    def test_configured_ffmpeg_folder_goes_first_on_path(self):
        tool = self.make_ffmpeg()
        Path(os.environ["KEYMASTER_SETTINGS"]).write_text(json.dumps({"ffmpeg": str(tool)}))
        env = {"KEYMASTER_SETTINGS": os.environ["KEYMASTER_SETTINGS"], "PATH": os.pathsep.join(["/a", "/b"])}
        self.assertEqual(settings.add_ffmpeg_to_path(env), str(tool.parent.resolve()))
        self.assertEqual(env["PATH"].split(os.pathsep), [str(tool.parent.resolve()), "/a", "/b"])
        settings.add_ffmpeg_to_path(env)
        self.assertEqual(env["PATH"].split(os.pathsep).count(str(tool.parent.resolve())), 1)

    def test_missing_or_absent_ffmpeg_leaves_path_alone(self):
        for stored in ({}, {"ffmpeg": str(self.tmp / "nope" / "ffmpeg")}, {"ffmpeg": 3}):
            Path(os.environ["KEYMASTER_SETTINGS"]).write_text(json.dumps(stored))
            env = {"KEYMASTER_SETTINGS": os.environ["KEYMASTER_SETTINGS"], "PATH": "/a"}
            self.assertIsNone(settings.add_ffmpeg_to_path(env))
            self.assertEqual(env["PATH"], "/a")

    def test_commands_see_the_configured_ffmpeg(self):
        tool = self.make_ffmpeg()
        Path(os.environ["KEYMASTER_SETTINGS"]).write_text(json.dumps({"ffmpeg": str(tool)}))
        with mock.patch("keymaster.doctor.run_doctor", return_value={"event": "doctor", "ok": True, "checks": []}):
            self.run_cli("doctor", "--json")
        self.assertEqual(os.environ["PATH"].split(os.pathsep)[0], str(tool.parent.resolve()))
