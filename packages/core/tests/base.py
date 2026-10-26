from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from keymaster import cli, keying, paths

from . import fake_runtime, fakes


class CoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="keymaster-test-"))
        self.addCleanup(self.cleanup)
        env = {k: v for k, v in os.environ.items() if not k.startswith("KEYMASTER_")}
        env["KEYMASTER_SETTINGS"] = str(self.tmp / "settings.json")
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.upstream = fakes.make_upstream(self.tmp / "upstream")
        for target, name, value in (
            (paths, "UPSTREAM_DIR", self.upstream),
            (keying, "import_upstream", fakes.loader()),
            (tempfile, "tempdir", str(self.tmp / "systemp")),
        ):
            p = mock.patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)
        (self.tmp / "systemp").mkdir()
        p = mock.patch.object(keying.shutil, "which", lambda name: "/usr/bin/" + name)
        p.start()
        self.addCleanup(p.stop)
        fake_runtime.reset()
        self.clip = fakes.make_clip(self.tmp / "shot.mp4")
        self.out = self.tmp / "out"

    def cleanup(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *argv):
        out = io.StringIO()
        with mock.patch("sys.stderr", io.StringIO()) as err:
            code = cli.main(list(argv), out=out)
        self.stderr = err.getvalue()
        text = out.getvalue()
        return code, text

    def run_events(self, *argv):
        code, text = self.run_cli(*argv)
        events = [json.loads(line) for line in text.splitlines() if line.strip()]
        return code, events

    def key(self, *extra, clip=None):
        return self.run_events("key", "--input", str(clip or self.clip), "--output-dir", str(self.out), *extra, "--json")
