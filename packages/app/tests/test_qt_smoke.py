from __future__ import annotations

import importlib.util
import json
import os
import time
import unittest
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

HAS_QT = importlib.util.find_spec("PySide6") is not None

from keymaster_app import clips
from keymaster_app.i18n import Translator, install

from tests.helpers import TempEnv


@unittest.skipUnless(HAS_QT, "PySide6 is not installed")
class MainWindowSmokeTest(TempEnv):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication
        from keymaster_app.ui.theme import apply_theme
        cls.app = QApplication.instance() or QApplication(["keymaster-app-test"])
        apply_theme(cls.app)

    def setUp(self) -> None:
        super().setUp()
        self.use_fake_core()
        install(Translator("en", core_dir=os.environ["KEYMASTER_CORE"]))

    def tearDown(self) -> None:
        install(Translator("en"))
        super().tearDown()

    def wait_for(self, condition, timeout: float = 30) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if condition():
                return True
            time.sleep(0.01)
        return False

    def test_run_clip_and_switch_language(self) -> None:
        from keymaster_app.ui.main_window import MainWindow
        window = MainWindow()
        window.show()
        try:
            self.assertEqual(window.start_button.text(), "Start")
            video = self.make_video()
            added = window.add_paths([str(video), str(self.tmp / "clips" / "readme.txt")])
            self.assertEqual(len(added), 1)
            self.assertEqual(window.queue_stack.currentIndex(), 1)
            clip = added[0]
            window.set_hint(clip.id, str(self.tmp / "hint.png"))
            self.assertEqual(window.items[clip.id].text(1), "hint.png")
            window.select_clip(clip.id)
            self.assertTrue(window.start())
            self.assertTrue(self.wait_for(lambda: not window.is_running() and clip.status == clips.DONE))
            self.app.processEvents()
            self.assertEqual(window.items[clip.id].text(2), "Done")
            self.assertEqual(window.bars[clip.id].value(), 1000)
            self.assertEqual(window.overall_bar.value(), 1000)
            self.assertTrue(window.preview_loaded())
            self.assertTrue(window.open_folder_button.isEnabled())
            self.assertTrue((video.parent / "shot_keyed" / "shot_cutout").is_dir())

            window.set_language("es-419")
            self.assertEqual(window.start_button.text(), "Iniciar")
            self.assertEqual(window.items[clip.id].text(2), "Listo")
            self.assertEqual(window.windowTitle(), "Keymaster")
            data = json.loads(Path(os.environ["KEYMASTER_SETTINGS"]).read_text(encoding="utf-8"))
            self.assertEqual(data["language"], "es-419")
            window.set_language("en")
            self.assertEqual(window.start_button.text(), "Start")
        finally:
            window.close()

    def test_cancel_from_window(self) -> None:
        from keymaster_app.ui.main_window import MainWindow
        os.environ["KEYMASTER_FAKE_DELAY"] = "0.3"
        window = MainWindow()
        window.show()
        try:
            (clip,) = window.add_paths([str(self.make_video())])
            self.assertTrue(window.start())
            self.assertTrue(self.wait_for(lambda: clip.progress > 0))
            window.cancel()
            self.assertTrue(self.wait_for(lambda: not window.is_running(), 15))
            self.app.processEvents()
            self.assertEqual(clip.status, clips.CANCELLED)
            self.assertEqual(window.items[clip.id].text(2), "Cancelled")
            self.assertTrue(window.start_button.isEnabled())
        finally:
            window.close()

    def test_failure_shows_error(self) -> None:
        from keymaster_app.ui.main_window import MainWindow
        os.environ["KEYMASTER_FAKE_FAIL"] = "out_of_memory"
        window = MainWindow()
        try:
            (clip,) = window.add_paths([str(self.make_video())])
            self.assertTrue(window.start())
            self.assertTrue(self.wait_for(lambda: not window.is_running() and clip.status == clips.FAILED))
            self.app.processEvents()
            self.assertTrue(window.items[clip.id].text(2))
            self.assertEqual(window.items[clip.id].toolTip(2), "fake failure out_of_memory")
        finally:
            window.close()

    def test_setup_check(self) -> None:
        from keymaster_app.ui.main_window import MainWindow
        window = MainWindow()
        try:
            window.show_setup_check()
            dialog = window.setup_dialog
            self.assertTrue(self.wait_for(lambda: dialog.result is not None))
            self.app.processEvents()
            self.assertEqual(dialog.status.text(), "Everything is ready.")
            window.set_language("es-419")
            self.assertEqual(dialog.status.text(), "Todo está listo.")
            dialog.close()
        finally:
            window.close()

    def test_setup_check_without_core(self) -> None:
        from keymaster_app.ui.main_window import MainWindow
        os.environ["KEYMASTER_CORE"] = str(self.tmp / "nowhere")
        window = MainWindow()
        try:
            window.add_paths([str(self.make_video())])
            self.assertFalse(window.start())
            self.assertIsNotNone(window.setup_dialog)
            self.assertEqual(window.setup_dialog.problem, "core")
            window.setup_dialog.close()
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
