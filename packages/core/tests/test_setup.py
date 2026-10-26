from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from unittest import mock

from keymaster import assets, paths
from keymaster.errors import KeymasterError

from .base import CoreCase


def fake_downloader(calls, fail=None):
    module = types.SimpleNamespace(CORRIDORKEY_REPO="repo/x")

    def writer(asset_id):
        def download(root, *rest):
            calls.append(asset_id)
            if fail == asset_id:
                raise OSError("network down")
            asset = next(a for a in assets.ASSETS if a["id"] == asset_id)
            for options in asset["files"]:
                path = Path(root) / options[0]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"m" * 1000)
        return download

    module.download_corridorkey = writer("corridorkey")
    module.download_cradio = writer("cradio")
    module.download_moge = writer("moge")
    module.download_rvm = writer("rvm")
    return module


class SetupTest(CoreCase):
    def empty_upstream(self, keep=()):
        root = self.tmp / "fresh"
        root.mkdir()
        for asset in assets.ASSETS:
            if asset["id"] in keep:
                for options in asset["files"]:
                    path = root / options[0]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"k")
        paths.UPSTREAM_DIR = root
        return root

    def run_setup(self, module):
        with mock.patch.object(assets, "load_downloader", lambda root: module):
            return self.run_events("setup", "--json")

    def test_downloads_everything_and_writes_settings(self):
        root = self.empty_upstream()
        calls = []
        code, events = self.run_setup(fake_downloader(calls))
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["corridorkey", "cradio", "moge", "rvm"])
        self.assertEqual(assets.missing(root), [])
        progress = [e for e in events if e["event"] == "progress"]
        self.assertTrue(all(set(e) == {"event", "phase", "fraction", "message_key"} for e in progress))
        self.assertTrue(all(e["phase"] == "download" for e in progress))
        fractions = [e["fraction"] for e in progress]
        self.assertEqual(fractions, sorted(fractions))
        self.assertEqual(fractions[-1], 1.0)
        keys = {e["message_key"] for e in progress}
        self.assertTrue({"core.progress.download_corridorkey", "core.progress.download_rvm", "core.progress.download_done"} <= keys)
        self.assertEqual(events[-1]["event"], "done")
        self.assertEqual(set(events[-1]), {"event", "outputs", "seconds"})
        stored = json.loads(Path(os.environ["KEYMASTER_SETTINGS"]).read_text())
        self.assertEqual(stored["python"], os.path.abspath(sys.executable))
        self.assertEqual(stored["core"], str(paths.CORE_DIR))

    def test_skips_what_is_present(self):
        self.empty_upstream(keep=("corridorkey", "moge"))
        calls = []
        code, _ = self.run_setup(fake_downloader(calls))
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["cradio", "rvm"])

    def test_nothing_to_do_needs_no_downloader(self):
        self.empty_upstream(keep=("corridorkey", "cradio", "moge", "rvm"))

        def refuse(root):
            raise AssertionError("downloader loaded")

        with mock.patch.object(assets, "load_downloader", refuse):
            code, events = self.run_events("setup", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["event"], "done")

    def test_download_failure(self):
        self.empty_upstream()
        code, events = self.run_setup(fake_downloader([], fail="moge"))
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["message_key"], "core.error.download_failed")
        self.assertEqual(events[-1]["params"], {"asset": "moge"})
        self.assertFalse(Path(os.environ["KEYMASTER_SETTINGS"]).exists())

    def test_real_script_loads_or_reports_dependency(self):
        if importlib.util.find_spec("huggingface_hub") is None:
            with self.assertRaises(KeymasterError) as ctx:
                assets.load_downloader(paths.CORE_DIR / "upstream")
            self.assertEqual(ctx.exception.message_key, "core.error.dependency_missing")
        else:
            module = assets.load_downloader(paths.CORE_DIR / "upstream")
            for name in ("download_corridorkey", "download_cradio", "download_moge", "download_rvm"):
                self.assertTrue(callable(getattr(module, name)))
