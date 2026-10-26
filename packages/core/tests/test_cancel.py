from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import unittest

from keymaster import paths

from .base import CoreCase


@unittest.skipIf(sys.platform == "win32", "POSIX signals")
class CancelTest(CoreCase):
    def test_sigterm_cleans_and_exits_130(self):
        systemp = self.tmp / "systemp"
        env = dict(os.environ, FAKE_UPSTREAM=str(self.upstream), FAKE_WINDOW_DELAY="0.4", TMPDIR=str(systemp))
        proc = subprocess.Popen(
            [sys.executable, str(paths.CORE_DIR / "tests" / "harness.py"), "key", "--input", str(self.clip),
             "--output-dir", str(self.out), "--json"],
            cwd=paths.CORE_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        events = []
        deadline = time.monotonic() + 30
        for line in proc.stdout:
            events.append(json.loads(line))
            if events[-1].get("phase") == "stage1":
                break
            self.assertLess(time.monotonic(), deadline)
        run_dirs = list((systemp / "keymaster-core").iterdir())
        self.assertEqual(len(run_dirs), 1)
        proc.send_signal(signal.SIGTERM)
        rest, err = proc.communicate(timeout=30)
        events += [json.loads(line) for line in rest.splitlines() if line.strip()]
        self.assertEqual(proc.returncode, 130, err)
        self.assertEqual(events[-1]["event"], "error")
        self.assertEqual(events[-1]["message_key"], "core.error.cancelled")
        self.assertEqual(list((systemp / "keymaster-core").iterdir()), [])

    def test_stdout_carries_only_json(self):
        env = dict(os.environ, FAKE_UPSTREAM=str(self.upstream), TMPDIR=str(self.tmp / "systemp"))
        proc = subprocess.run(
            [sys.executable, str(paths.CORE_DIR / "tests" / "harness.py"), "key", "--input", str(self.clip),
             "--output-dir", str(self.out), "--json"],
            cwd=paths.CORE_DIR, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertTrue(all(isinstance(json.loads(line), dict) for line in lines))
        self.assertIn("window 1/", proc.stderr)
        self.assertEqual(json.loads(lines[-1])["event"], "done")
