import json
import re
import unittest
from pathlib import Path

from keymaster import i18n
from tests.helpers import PACKAGE, ROOT, scratch


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def write(directory: Path, lang: str, table: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{lang}.json").write_text(json.dumps(table), encoding="utf-8")


class Tables(unittest.TestCase):
    def test_dev_dirs_point_at_the_repo(self):
        dirs = i18n.table_dirs()
        self.assertEqual(dirs, [PACKAGE / "i18n", ROOT / "packages" / "core" / "i18n"])

    def test_bundled_dirs_win(self):
        with scratch() as tmp:
            here = Path(tmp) / "keymaster"
            write(here / "i18n", "en", {})
            self.assertEqual(i18n.table_dirs(here), [here / "i18n", here / "i18n" / "core"])

    def test_real_tables_have_same_keys(self):
        en = json.loads((PACKAGE / "i18n" / "en.json").read_text(encoding="utf-8"))
        es = json.loads((PACKAGE / "i18n" / "es-419.json").read_text(encoding="utf-8"))
        self.assertEqual(set(en), set(es))
        for key in en:
            self.assertEqual(set(re.findall(r"\{(\w+)\}", en[key])), set(re.findall(r"\{(\w+)\}", es[key])), key)

    def test_loads_real_tables(self):
        tr = i18n.Translator(language=lambda: "es-419")
        self.assertEqual(tr("blender.cancel.label"), "Cancelar")
        self.assertEqual(i18n.Translator(language=lambda: "en")("blender.cancel.label"), "Cancel")


class Translate(unittest.TestCase):
    def setUp(self):
        self.tmp = scratch()
        base = Path(self.tmp.name)
        write(base / "host", "en", {"blender.a": "Hello {name}", "blender.only_en": "English only"})
        write(base / "host", "es-419", {"blender.a": "Hola {name}"})
        write(base / "core", "en", {"core.error.x": "Broken {what}"})
        write(base / "core", "es-419", {"core.error.x": "Roto {what}"})
        self.dirs = [base / "host", base / "core"]
        self.language = "en"
        self.clock = Clock()
        self.tr = i18n.Translator(self.dirs, language=lambda: self.language, clock=self.clock)

    def tearDown(self):
        self.tmp.cleanup()

    def test_placeholders(self):
        self.assertEqual(self.tr("blender.a", name="Ana"), "Hello Ana")
        self.assertEqual(self.tr("blender.a"), "Hello {name}")

    def test_core_keys_and_fallbacks(self):
        self.language = "es-419"
        self.assertEqual(self.tr("blender.a", name="Ana"), "Hola Ana")
        self.assertEqual(self.tr.translate("core.error.x", {"what": "GPU"}), "Roto GPU")
        self.assertEqual(self.tr("blender.only_en"), "English only")
        self.assertEqual(self.tr("blender.missing"), "blender.missing")
        self.assertTrue(self.tr.has("core.error.x"))
        self.assertFalse(self.tr.has("core.error.y"))
        self.assertFalse(self.tr.has(None))

    def test_language_refreshes_on_a_timer(self):
        self.assertEqual(self.tr("blender.a", name="x"), "Hello x")
        self.language = "es-419"
        self.clock.now += i18n.REFRESH_SECONDS / 2
        self.assertEqual(self.tr("blender.a", name="x"), "Hello x")
        self.clock.now += i18n.REFRESH_SECONDS
        self.assertEqual(self.tr("blender.a", name="x"), "Hola x")

    def test_invalidate_applies_at_once(self):
        self.tr("blender.a")
        self.language = "es-419"
        self.tr.invalidate()
        self.assertEqual(self.tr("blender.a", name="x"), "Hola x")

    def test_unknown_language_falls_back(self):
        self.language = "fr"
        self.assertEqual(self.tr("blender.a", name="x"), "Hello x")


if __name__ == "__main__":
    unittest.main()
