from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
REPO = APP.parents[1]
FAKE_CORE = REPO / "packages" / "core" / "testing" / "fake_core"


class TempEnv(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="keymaster-app-test-"))
        self._saved = {k: os.environ.get(k) for k in (
            "KEYMASTER_SETTINGS", "KEYMASTER_PYTHON", "KEYMASTER_CORE", "KEYMASTER_LANGUAGE",
            "KEYMASTER_FAKE_FAIL", "KEYMASTER_FAKE_DELAY", "XDG_CONFIG_HOME",
            "LANG", "LC_ALL", "LC_MESSAGES", "LANGUAGE")}
        for key in self._saved:
            os.environ.pop(key, None)
        os.environ["KEYMASTER_SETTINGS"] = str(self.tmp / "settings.json")

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def use_fake_core(self) -> None:
        os.environ["KEYMASTER_PYTHON"] = sys.executable
        os.environ["KEYMASTER_CORE"] = str(FAKE_CORE)

    def make_video(self, name: str = "shot.mp4") -> Path:
        path = self.tmp / "clips" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"not really a video")
        return path

    def make_frames(self, name: str = "plate", count: int = 3) -> Path:
        folder = self.tmp / "clips" / name
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            (folder / f"{name}.{i:04d}.png").write_bytes(b"png")
        return folder
