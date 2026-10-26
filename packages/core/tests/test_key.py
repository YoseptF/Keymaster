from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

from keymaster import keying
from keymaster.errors import KeymasterError

from . import fake_runtime, fakes
from .base import CoreCase
from .fakes import OutOfMemoryError

REAL_IMPORT = keying.import_upstream
EVENT_FIELDS = {
    "start": {"event", "input", "first_frame", "frames", "width", "height", "fps"},
    "progress": {"event", "phase", "fraction", "message_key"},
    "output": {"event", "kind", "type", "path", "first_frame", "frames"},
    "done": {"event", "outputs", "seconds"},
    "error": {"event", "message_key", "params", "detail"},
}


class KeyMappingTest(CoreCase):
    def run_args(self):
        return [c for c in fake_runtime.CALLS if c[0] == "run_inference"][-1][1]

    def test_defaults_map_to_upstream(self):
        code, _ = self.key()
        self.assertEqual(code, 0)
        call = self.run_args()
        cfg = call["cfg"]
        self.assertEqual(cfg.output_format, "exr")
        self.assertEqual(cfg.outputs, {"alpha", "fg", "cutout"})
        self.assertEqual(cfg.despill_strength, 0.5)
        self.assertEqual(cfg.hint_quality, 0.95)
        self.assertEqual(cfg.num_frames, -1)
        self.assertTrue(cfg.auto_vram)
        self.assertFalse(cfg.low_vram)
        self.assertEqual(cfg.exr_dtype, "half")
        self.assertIsNone(call["initial_hint_path"])
        self.assertIsNone(call["hint_video_path"])
        self.assertTrue(str(cfg.temp_dir).startswith(str(self.tmp / "systemp" / "keymaster-core")))

    def test_options_map_to_upstream(self):
        hint = self.tmp / "hint.png"
        hint.write_bytes(b"h")
        hint_video = fakes.make_clip(self.tmp / "hint.mp4")
        code, _ = self.key("--format", "video", "--despill", "0.8", "--hint-quality", "0.5", "--frames", "6",
                           "--low-vram", "--outputs", "alpha", "checker", "--hint-first-frame", str(hint),
                           "--hint-video", str(hint_video))
        self.assertEqual(code, 0)
        call = self.run_args()
        cfg = call["cfg"]
        self.assertEqual(cfg.output_format, "video")
        self.assertEqual(cfg.despill_strength, 0.8)
        self.assertEqual(cfg.hint_quality, 0.5)
        self.assertEqual(cfg.num_frames, 6)
        self.assertTrue(cfg.low_vram)
        self.assertFalse(cfg.auto_vram)
        self.assertEqual(cfg.outputs, {"alpha", "checker"})
        self.assertEqual(call["initial_hint_path"], str(hint))
        self.assertEqual(call["hint_video_path"], str(hint_video))

    def test_relative_paths_become_absolute(self):
        cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, cwd)
        code, events = self.run_events("key", "--input", "shot.mp4", "--output-dir", "out", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(events[0]["input"], str(self.clip))
        self.assertTrue(all(Path(e["path"]).is_absolute() for e in events if e["event"] == "output"))


class KeyEventsTest(CoreCase):
    def test_stream_shape(self):
        code, events = self.key()
        self.assertEqual(code, 0)
        self.assertEqual(events[0]["event"], "start")
        self.assertEqual(events[-1]["event"], "done")
        for event in events:
            self.assertEqual(set(event), EVENT_FIELDS[event["event"]] | ({"pattern"} if event.get("type") == "image_sequence" else set()))
        self.assertEqual(events[0], {"event": "start", "input": str(self.clip), "first_frame": 0, "frames": 20,
                                     "width": 64, "height": 36, "fps": 24.0})
        outputs = [e for e in events if e["event"] == "output"]
        self.assertEqual(events[-1]["outputs"], outputs)

    def test_progress_is_monotonic_and_covers_phases(self):
        for extra in ((), ("--low-vram",), ("--format", "video")):
            _, events = self.key(*extra)
            progress = [e for e in events if e["event"] == "progress"]
            fractions = [e["fraction"] for e in progress]
            self.assertEqual(fractions, sorted(fractions), extra)
            self.assertEqual(fractions[-1], 1.0)
            self.assertEqual({e["phase"] for e in progress}, {"load", "prepass", "stage1", "stage2", "write"})
            for e in progress:
                self.assertEqual(e["message_key"], f"core.progress.{e['phase']}")
            last_progress = max(i for i, e in enumerate(events) if e["event"] == "progress")
            first_output = min(i for i, e in enumerate(events) if e["event"] == "output")
            self.assertLess(last_progress, first_output)

    def test_progress_moves_during_stage1(self):
        fake_runtime.AUTO_CHUNK = 4
        _, events = self.key()
        stage1 = [e["fraction"] for e in events if e["event"] == "progress" and e["phase"] == "stage1"]
        self.assertGreater(len(set(stage1)), 2)

    def test_exr_outputs_match_upstream_naming(self):
        code, events = self.key("--outputs", "alpha", "fg", "cutout", "checker", "--despill", "0.25")
        self.assertEqual(code, 0)
        outputs = {e["kind"]: e for e in events if e["event"] == "output"}
        self.assertEqual(list(outputs), ["alpha", "fg", "cutout", "checker"])
        for kind, suffix in (("alpha", "alpha"), ("fg", "fg"), ("cutout", "cutout"), ("checker", "checker_comp_despill025")):
            item = outputs[kind]
            self.assertEqual(item["type"], "image_sequence")
            self.assertEqual(item["path"], str(self.out / f"shot_{suffix}_exr"))
            self.assertEqual(item["pattern"], str(self.out / f"shot_{suffix}_exr" / f"{suffix}_%06d.exr"))
            self.assertEqual((item["first_frame"], item["frames"]), (0, 20))
            for f in range(20):
                self.assertTrue(Path(item["pattern"] % f).is_file())

    def test_video_outputs_match_upstream_naming(self):
        code, events = self.key("--format", "video", "--outputs", "alpha", "cutout", "checker")
        self.assertEqual(code, 0)
        outputs = {e["kind"]: e for e in events if e["event"] == "output"}
        self.assertEqual(outputs["alpha"]["path"], str(self.out / "shot_alpha.mp4"))
        self.assertEqual(outputs["cutout"]["path"], str(self.out / "shot_cutout.mov"))
        self.assertEqual(outputs["checker"]["path"], str(self.out / "shot_checker_comp_despill050.mp4"))
        for item in outputs.values():
            self.assertEqual(item["type"], "video")
            self.assertNotIn("pattern", item)
            self.assertTrue(Path(item["path"]).is_file())

    def test_start_frame_and_frames(self):
        code, events = self.key("--start-frame", "5", "--frames", "6", "--outputs", "alpha")
        self.assertEqual(code, 0)
        self.assertEqual((events[0]["first_frame"], events[0]["frames"]), (5, 6))
        item = [e for e in events if e["event"] == "output"][0]
        self.assertEqual((item["first_frame"], item["frames"]), (5, 6))
        files = sorted(p.name for p in Path(item["path"]).iterdir())
        self.assertEqual(files, [f"alpha_{i:06d}.exr" for i in range(5, 11)])

    def test_start_frame_aligns_hints(self):
        hint_video = fakes.make_clip(self.tmp / "hint.mp4")
        self.key("--start-frame", "3", "--hint-video", str(hint_video))
        reader = [c for c in fake_runtime.CALLS if c[0] == "hint_reader"][-1][1]
        self.assertEqual(reader.start_frame, 3)
        hints = self.tmp / "hints"
        hints.mkdir()
        for i in range(20):
            (hints / f"h_{i:04d}.png").write_bytes(b"h")
        self.key("--start-frame", "3", "--frames", "4", "--hint-video", str(hints))
        reader = [c for c in fake_runtime.CALLS if c[0] == "hint_reader"][-1][1]
        self.assertEqual(reader.paths[0], str(hints / "h_0003.png"))

    def test_start_frame_clamps_frames_to_the_end(self):
        _, events = self.key("--start-frame", "15", "--frames", "100", "--outputs", "alpha")
        self.assertEqual((events[0]["first_frame"], events[0]["frames"]), (15, 5))

    def test_start_frame_on_frame_directory(self):
        frames = self.tmp / "plate"
        frames.mkdir()
        for i in range(12):
            (frames / f"p_{i:04d}.png").write_bytes(b"p")
        code, events = self.key("--start-frame", "4", "--frames", "3", "--outputs", "alpha", clip=frames)
        self.assertEqual(code, 0)
        self.assertEqual((events[0]["first_frame"], events[0]["frames"]), (4, 3))
        item = [e for e in events if e["event"] == "output"][0]
        self.assertEqual(item["path"], str(self.out / "plate_alpha_exr"))
        self.assertEqual(sorted(p.name for p in Path(item["path"]).iterdir()), [f"alpha_{i:06d}.exr" for i in (4, 5, 6)])

    def test_human_mode_writes_only_stderr(self):
        code, text = self.run_cli("key", "--input", str(self.clip), "--output-dir", str(self.out))
        self.assertEqual(code, 0)
        self.assertEqual(text, "")
        self.assertIn("100%", self.stderr)

    def test_temp_dir_removed(self):
        self.key()
        root = self.tmp / "systemp" / "keymaster-core"
        self.assertEqual(list(root.iterdir()), [])

    def test_stale_temp_dirs_swept(self):
        root = self.tmp / "systemp" / "keymaster-core"
        stale = root / "run-999999999"
        stale.mkdir(parents=True)
        (stale / "x.f16").write_bytes(b"x")
        self.key()
        self.assertFalse(stale.exists())


class KeyErrorTest(CoreCase):
    def assert_error(self, events, code, key):
        self.assertEqual(code, 130 if key == "core.error.cancelled" else 1)
        self.assertEqual(events[-1]["event"], "error")
        self.assertEqual(set(events[-1]), EVENT_FIELDS["error"])
        self.assertEqual(events[-1]["message_key"], key)
        self.assertTrue(events[-1]["detail"])

    def test_no_gpu(self):
        with mock.patch.object(keying, "import_upstream", fakes.loader(cuda=False)):
            code, events = self.key()
        self.assert_error(events, code, "core.error.no_gpu")

    def test_ffmpeg_missing_for_video(self):
        with mock.patch.object(keying.shutil, "which", lambda name: None):
            code, events = self.key("--format", "video")
            self.assert_error(events, code, "core.error.ffmpeg_missing")
            code, events = self.key("--format", "exr")
            self.assertEqual(code, 0)

    def test_weights_missing(self):
        (self.upstream / "vfms" / "moge" / "model.pt").unlink()
        code, events = self.key()
        self.assert_error(events, code, "core.error.weights_missing")
        self.assertIn("moge", events[-1]["params"]["missing"])

    def test_input_missing_or_unreadable(self):
        code, events = self.key(clip=self.tmp / "nope.mp4")
        self.assert_error(events, code, "core.error.input_unreadable")
        self.assertEqual(events[-1]["params"]["path"], str(self.tmp / "nope.mp4"))
        bad = self.tmp / "bad.mp4"
        bad.write_bytes(b"\x00garbage")
        code, events = self.key(clip=bad)
        self.assert_error(events, code, "core.error.input_unreadable")
        empty = self.tmp / "empty"
        empty.mkdir()
        code, events = self.key(clip=empty)
        self.assert_error(events, code, "core.error.input_unreadable")

    def test_missing_hint(self):
        code, events = self.key("--hint-video", str(self.tmp / "nohint.mp4"))
        self.assert_error(events, code, "core.error.input_unreadable")

    def test_start_frame_past_end(self):
        code, events = self.key("--start-frame", "20")
        self.assert_error(events, code, "core.error.invalid_arguments")

    def test_bad_arguments(self):
        for extra in (("--despill", "2"), ("--frames", "-1"), ("--format", "png"), ("--outputs", "matte")):
            code, events = self.key(*extra)
            self.assert_error(events, code, "core.error.invalid_arguments")
        code, events = self.run_events("key", "--json")
        self.assert_error(events, code, "core.error.invalid_arguments")
        code, events = self.run_events("frobnicate", "--json")
        self.assert_error(events, code, "core.error.invalid_arguments")

    def test_output_unwritable(self):
        blocker = self.tmp / "file"
        blocker.write_bytes(b"x")
        code, events = self.run_events("key", "--input", str(self.clip), "--output-dir", str(blocker / "sub"), "--json")
        self.assert_error(events, code, "core.error.output_unwritable")

    def test_runtime_failures(self):
        cases = (
            (OutOfMemoryError("CUDA out of memory. Tried to allocate 20.00 GiB"), "core.error.out_of_memory"),
            (FileNotFoundError("ffmpeg binary not found: ffmpeg"), "core.error.ffmpeg_missing"),
            (RuntimeError("ffmpeg writer failed with exit code 1: x"), "core.error.encode_failed"),
            (RuntimeError("shot.mp4: failed decoding frame 7"), "core.error.unknown"),
            (OSError(28, "No space left on device"), "core.error.disk_full"),
            (KeyboardInterrupt(), "core.error.cancelled"),
            (ValueError("surprise"), "core.error.unknown"),
        )
        for exc, key in cases:
            fake_runtime.FAIL = exc
            code, events = self.key()
            self.assert_error(events, code, key)
            self.assertEqual(list((self.tmp / "systemp" / "keymaster-core").iterdir()), [])

    def test_missing_torch(self):
        def broken():
            from keymaster.errors import KeymasterError
            raise KeymasterError(message_key="core.error.dependency_missing", params={"name": "torch"}, detail="x")
        with mock.patch.object(keying, "import_upstream", broken):
            code, events = self.key()
        self.assert_error(events, code, "core.error.dependency_missing")


class ImportWithoutTorchTest(CoreCase):
    def test_real_loader_reports_missing_torch(self):
        with mock.patch.dict("sys.modules", {"torch": None}):
            with self.assertRaises(KeymasterError) as ctx:
                REAL_IMPORT()
        self.assertEqual(ctx.exception.message_key, "core.error.dependency_missing")
        self.assertEqual(ctx.exception.params, {"name": "torch"})
