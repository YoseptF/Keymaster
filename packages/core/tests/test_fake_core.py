from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from keymaster import cli, paths

from .base import CoreCase

FAKE_ROOT = paths.CORE_DIR / "testing" / "fake_core"


def load_fake():
    spec = importlib.util.spec_from_file_location("keymaster_fake_main", FAKE_ROOT / "keymaster" / "__main__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def describe(parser: argparse.ArgumentParser) -> dict:
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    shape = {}
    for name, child in sub.choices.items():
        shape[name] = sorted(
            (tuple(a.option_strings) or (a.dest,), a.dest, repr(a.default), repr(a.choices), repr(a.nargs),
             getattr(a.type, "__name__", repr(a.type)), a.required, type(a).__name__)
            for a in child._actions if not isinstance(a, argparse._HelpAction))
    return shape


class FakeCoreParityTest(CoreCase):
    def run_fake(self, *argv, env=None):
        full_env = dict(os.environ, **(env or {}))
        proc = subprocess.run([sys.executable, "-m", "keymaster", *argv], cwd=FAKE_ROOT, env=full_env,
                              capture_output=True, text=True, timeout=60)
        return proc.returncode, [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]

    def test_same_cli(self):
        self.assertEqual(describe(load_fake().build_parser()), describe(cli.build_parser()))

    def fields(self, events):
        found = {}
        for event in events:
            found.setdefault((event["event"], event.get("type")), set(event))
        return found

    def test_same_key_events(self):
        for fmt in ("exr", "video"):
            argv = ("key", "--input", str(self.clip), "--output-dir", str(self.tmp / f"o_{fmt}"),
                    "--format", fmt, "--start-frame", "2", "--frames", "3", "--json")
            fake_code, fake_events = self.run_fake(*argv)
            code, events = self.run_events(*argv)
            self.assertEqual((fake_code, code), (0, 0))
            self.assertEqual(self.fields(fake_events), self.fields(events))
            fake_out = [e for e in fake_events if e["event"] == "output"]
            out = [e for e in events if e["event"] == "output"]
            self.assertEqual([(e["kind"], e["type"], e["first_frame"], e["frames"]) for e in fake_out],
                             [(e["kind"], e["type"], e["first_frame"], e["frames"]) for e in out])
            self.assertEqual({e["phase"] for e in fake_events if e["event"] == "progress"},
                             {e["phase"] for e in events if e["event"] == "progress"})

    def test_same_errors_and_exit_codes(self):
        argv = ("key", "--input", str(self.clip), "--output-dir", str(self.out), "--json")
        for code_name, expected in (("out_of_memory", 1), ("cancelled", 130)):
            fake_code, fake_events = self.run_fake(*argv, env={"KEYMASTER_FAKE_FAIL": code_name})
            self.assertEqual(fake_code, expected)
            self.assertEqual(set(fake_events[-1]), {"event", "message_key", "params", "detail"})
        _, events = self.run_events("key", "--input", str(self.tmp / "missing.mp4"), "--output-dir", str(self.out), "--json")
        self.assertEqual(set(events[-1]), {"event", "message_key", "params", "detail"})

    def test_same_doctor_setup_settings(self):
        fake_code, fake_events = self.run_fake("doctor", "--json", env={"KEYMASTER_FAKE_FAIL": "no_gpu"})
        self.assertEqual(fake_code, 1)
        self.assertEqual(set(fake_events[0]), {"event", "ok", "checks"})
        self.assertEqual([c["id"] for c in fake_events[0]["checks"]], ["gpu", "ffmpeg", "weights", "torch"])
        _, fake_setup = self.run_fake("setup", "--json")
        self.assertEqual({e["phase"] for e in fake_setup if e["event"] == "progress"}, {"download"})
        self.assertEqual(fake_setup[-1]["event"], "done")
        for stored, env in ((None, {"KEYMASTER_LANGUAGE": "es-419"}), ("auto", {"LANG": "es_MX.UTF-8"}),
                            ("en", {"LANG": "es_MX.UTF-8"}), ("fr", {"LC_ALL": "es_CL"}), (None, {"LANG": "C"})):
            Path(os.environ["KEYMASTER_SETTINGS"]).write_text(json.dumps({"language": stored} if stored else {}))
            proc = subprocess.run([sys.executable, "-m", "keymaster", "settings", "get", "--json"], cwd=FAKE_ROOT,
                                  env=dict(os.environ, **env), capture_output=True, text=True, timeout=60)
            with mock.patch.dict(os.environ, env):
                _, mine = self.run_cli("settings", "get", "--json")
            self.assertEqual(json.loads(proc.stdout), json.loads(mine), (stored, env))

    def test_fake_keys_exist_in_core_tables(self):
        table = json.loads((paths.I18N_DIR / "en.json").read_text())
        source = (FAKE_ROOT / "keymaster" / "__main__.py").read_text()
        import re
        for key in re.findall(r'"(core\.[a-z_]+\.[a-z_]+)"', source):
            self.assertIn(key, table)
        for phase in ("load", "prepass", "stage1", "stage2", "write"):
            self.assertIn(f"core.progress.{phase}", table)
        for check in ("gpu", "ffmpeg", "weights", "torch"):
            self.assertIn(f"core.doctor.{check}_ok", table)
            self.assertIn(f"core.doctor.{check}_missing", table)
