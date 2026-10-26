import sys
import time
import unittest
from pathlib import Path

from keymaster import events, runner
from tests.helpers import FAKE_CORE, env, scratch


class Command(unittest.TestCase):
    def test_full_command(self):
        options = runner.KeyOptions(input="/in/clip.mov", output_dir="/out", hint_first_frame="/in/hint.png",
                                    hint_quality=0.9, despill=0.25, format="video",
                                    outputs=("cutout", "alpha", "bogus"), low_vram=True, frames=12)
        self.assertEqual(runner.key_command("/py", options), [
            "/py", "-m", "keymaster", "key", "--input", "/in/clip.mov", "--output-dir", "/out",
            "--hint-first-frame", "/in/hint.png", "--hint-quality", "0.9", "--despill", "0.25", "--format", "video",
            "--outputs", "alpha", "cutout", "--frames", "12", "--low-vram", "--json"])

    def test_defaults(self):
        argv = runner.key_command("py", runner.KeyOptions(input="/a", output_dir="/b", format="nope"))
        self.assertEqual(argv[argv.index("--format") + 1], "exr")
        self.assertNotIn("--hint-first-frame", argv)
        self.assertNotIn("--frames", argv)
        self.assertEqual(argv[-1], "--json")

    def test_doctor(self):
        self.assertEqual(runner.doctor_command("py"), ["py", "-m", "keymaster", "doctor", "--json"])

    def test_run_dir_name(self):
        self.assertEqual(runner.run_dir_name("My clip.mp4", "20260101-000000"), "My_clip_mp4_20260101-000000")
        self.assertEqual(runner.run_dir_name("///", "s"), "strip_s")

    def test_unique_dir(self):
        with scratch() as tmp:
            self.assertEqual(runner.unique_dir(tmp, "a"), str(Path(tmp) / "a"))
            (Path(tmp) / "a").mkdir()
            (Path(tmp) / "a-2").mkdir()
            self.assertEqual(runner.unique_dir(tmp, "a"), str(Path(tmp) / "a-3"))


class FakeCore(unittest.TestCase):
    def setUp(self):
        self.tmp = scratch()
        self.out = Path(self.tmp.name) / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def key(self, fmt="exr", **extra):
        options = runner.KeyOptions(input=str(Path(self.tmp.name) / "clip.mp4"), output_dir=str(self.out),
                                    format=fmt, frames=3)
        return runner.CoreRun(runner.key_command(sys.executable, options), cwd=str(FAKE_CORE), env=env(**extra))

    def test_key_sequence(self):
        state = self.key().start().wait()
        self.assertEqual(state.status, events.DONE)
        self.assertEqual(state.start["frames"], 3)
        self.assertEqual(state.fraction, 1.0)
        outputs = state.final_outputs()
        self.assertEqual([o["kind"] for o in outputs], ["alpha", "fg", "cutout"])
        for item in outputs:
            self.assertEqual(item["type"], "image_sequence")
            for n in range(item["first_frame"], item["first_frame"] + item["frames"]):
                self.assertTrue(Path(item["pattern"] % n).is_file())

    def test_key_video(self):
        state = self.key("video").start().wait()
        self.assertEqual({o["type"] for o in state.final_outputs()}, {"video"})

    def test_failure(self):
        state = self.key(KEYMASTER_FAKE_FAIL="no_gpu").start().wait()
        self.assertEqual(state.status, events.FAILED)
        self.assertEqual(state.error["message_key"], "core.error.no_gpu")

    def test_cancel(self):
        run = self.key(KEYMASTER_FAKE_DELAY="0.5").start()
        deadline = time.monotonic() + 10
        while run.step().fraction == 0 and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertGreater(run.state.fraction, 0)
        run.cancel()
        state = run.wait(timeout=10)
        self.assertEqual(state.status, events.CANCELLED)
        self.assertIsNotNone(run.process.poll())

    def test_missing_python(self):
        run = runner.CoreRun(["/nonexistent/python", "-m", "keymaster", "doctor", "--json"], cwd=str(FAKE_CORE))
        state = run.start().step()
        self.assertEqual(state.status, events.FAILED)
        self.assertEqual(state.error["message_key"], "blender.error.python_missing")

    def test_crash_keeps_stderr(self):
        run = runner.CoreRun([sys.executable, "-c", "import sys; sys.stderr.write('kaboom\\n'); sys.exit(3)"],
                             cwd=str(FAKE_CORE), env=env())
        state = run.start().wait()
        self.assertEqual(state.status, events.FAILED)
        self.assertIn("kaboom", state.error["detail"])

    def test_doctor(self):
        run = runner.CoreRun(runner.doctor_command(sys.executable), cwd=str(FAKE_CORE), env=env())
        state = run.start().wait()
        self.assertEqual(state.status, events.DONE)
        self.assertTrue(state.doctor["ok"])
        self.assertEqual(len(state.doctor["checks"]), 4)


if __name__ == "__main__":
    unittest.main()
