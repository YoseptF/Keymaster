from __future__ import annotations

from unittest import mock

from keymaster import doctor

from . import fakes
from .base import CoreCase


class DoctorTest(CoreCase):
    def run_doctor(self, cuda=True, ffmpeg="/usr/bin/ffmpeg", torch=True):
        def load():
            if not torch:
                raise ModuleNotFoundError("No module named 'torch'", name="torch")
            return fakes.make_torch(cuda)

        with mock.patch.object(doctor, "import_torch", load), mock.patch.object(doctor.shutil, "which", lambda n: ffmpeg):
            return self.run_events("doctor", "--json")

    def test_all_ok(self):
        code, events = self.run_doctor()
        self.assertEqual(code, 0)
        self.assertEqual(len(events), 1)
        report = events[0]
        self.assertEqual(set(report), {"event", "ok", "checks"})
        self.assertTrue(report["ok"])
        self.assertEqual([c["id"] for c in report["checks"]], ["gpu", "ffmpeg", "weights", "torch"])
        for check in report["checks"]:
            self.assertEqual(set(check), {"id", "ok", "message_key", "params"})
            self.assertEqual(check["message_key"], f"core.doctor.{check['id']}_ok")
        self.assertEqual(report["checks"][0]["params"], {"name": "Fake GPU", "memory": 24.0})

    def test_failures(self):
        (self.upstream / "vfms" / "rvm" / "pretrain_rvm_small16_256_204031069.npz").unlink()
        code, events = self.run_doctor(cuda=False, ffmpeg=None)
        self.assertEqual(code, 1)
        report = events[-1]
        self.assertFalse(report["ok"])
        keys = {c["id"]: c["message_key"] for c in report["checks"]}
        self.assertEqual(keys, {"gpu": "core.doctor.gpu_missing", "ffmpeg": "core.doctor.ffmpeg_missing",
                                "weights": "core.doctor.weights_missing", "torch": "core.doctor.torch_ok"})
        self.assertEqual(report["checks"][2]["params"], {"missing": "rvm"})

    def test_without_torch(self):
        code, events = self.run_doctor(torch=False)
        self.assertEqual(code, 1)
        keys = {c["id"]: c["message_key"] for c in events[-1]["checks"]}
        self.assertEqual(keys["torch"], "core.doctor.torch_missing")
        self.assertEqual(keys["gpu"], "core.doctor.gpu_missing")
