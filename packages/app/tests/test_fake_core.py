from __future__ import annotations

import os
import sys
import threading
import time
import unittest
from pathlib import Path

from keymaster_app import clips
from keymaster_app.batch import BATCH_FINISHED, CLIP_EVENT, Batch, run_doctor
from keymaster_app.commands import KeyOptions
from keymaster_app.media import preview_source

from tests.helpers import FAKE_CORE, TempEnv


class FakeCoreTest(TempEnv):
    def run_batch(self, queue: clips.ClipQueue, options: KeyOptions, env: dict | None = None,
                  cancel_after_event: bool = False, timeout: float = 30) -> tuple[Batch, list]:
        seen: list = []
        finished = threading.Event()
        holder: dict = {}

        def notify(kind: str, clip_id) -> None:
            seen.append((kind, clip_id))
            if kind == CLIP_EVENT and cancel_after_event and not holder.get("cancelled"):
                holder["cancelled"] = True
                holder["at"] = time.monotonic()
                threading.Thread(target=holder["batch"].cancel).start()
            if kind == BATCH_FINISHED:
                finished.set()

        batch = Batch(queue, options, sys.executable, str(FAKE_CORE), notify=notify, env=env)
        holder["batch"] = batch
        batch.start()
        self.assertTrue(finished.wait(timeout), "batch did not finish")
        self.assertTrue(batch.join(10))
        if cancel_after_event:
            self.assertLess(time.monotonic() - holder["at"], 10)
        return batch, seen

    def env(self, **extra: str) -> dict:
        env = dict(os.environ)
        env.update(extra)
        return env

    def test_success_writes_outputs(self) -> None:
        queue = clips.ClipQueue()
        video = self.make_video()
        frames = self.make_frames()
        a, b = queue.add([str(video), str(frames)])
        queue.set_hint(a.id, str(self.tmp / "clips" / "hint.png"))
        _, seen = self.run_batch(queue, KeyOptions(outputs=("alpha", "cutout", "checker")))
        self.assertEqual([a.status, b.status], [clips.DONE, clips.DONE])
        self.assertEqual(a.output_dir, str(video.parent / "shot_keyed"))
        self.assertEqual(b.output_dir, str(frames.parent / "plate_keyed"))
        self.assertEqual(sorted(o["kind"] for o in a.outputs), ["alpha", "checker", "cutout"])
        self.assertEqual(a.frames, 4)
        self.assertEqual(queue.overall(), 1.0)
        source = preview_source(a.outputs)
        self.assertIsNotNone(source)
        self.assertIn("cutout", Path(source).name)
        self.assertTrue(Path(source).is_file())
        self.assertEqual(seen[-1], (BATCH_FINISHED, None))

    def test_custom_root_and_video_format(self) -> None:
        queue = clips.ClipQueue()
        (clip,) = queue.add([str(self.make_video("take.mov"))])
        root = self.tmp / "renders"
        self.run_batch(queue, KeyOptions(format="video", output_root=str(root)))
        self.assertEqual(clip.status, clips.DONE)
        self.assertTrue((root / "take_keyed" / "take_cutout.mov").is_file())
        self.assertIsNone(preview_source(clip.outputs))

    def test_failure_reports_core_error(self) -> None:
        queue = clips.ClipQueue()
        a, b = queue.add([str(self.make_video("a.mp4")), str(self.make_video("b.mp4"))])
        self.run_batch(queue, KeyOptions(), env=self.env(KEYMASTER_FAKE_FAIL="no_gpu"))
        for clip in (a, b):
            self.assertEqual(clip.status, clips.FAILED)
            self.assertEqual(clip.error["message_key"], "core.error.no_gpu")
            self.assertEqual(clip.error["detail"], "fake failure no_gpu")

    def test_cancel_mid_run(self) -> None:
        queue = clips.ClipQueue()
        a, b = queue.add([str(self.make_video("a.mp4")), str(self.make_video("b.mp4"))])
        batch, _ = self.run_batch(queue, KeyOptions(), env=self.env(KEYMASTER_FAKE_DELAY="0.5"), cancel_after_event=True)
        self.assertTrue(batch.cancelled)
        self.assertEqual(a.status, clips.CANCELLED)
        self.assertEqual(b.status, clips.QUEUED)
        self.assertLess(a.progress, 1.0)
        self.assertEqual(queue.prepare_run(), 2)

    def test_missing_python_fails_cleanly(self) -> None:
        queue = clips.ClipQueue()
        (clip,) = queue.add([str(self.make_video())])
        finished = threading.Event()
        batch = Batch(queue, KeyOptions(), str(self.tmp / "no-python"), str(FAKE_CORE),
                      notify=lambda kind, _: finished.set() if kind == BATCH_FINISHED else None)
        batch.start()
        self.assertTrue(finished.wait(10))
        self.assertEqual(clip.status, clips.FAILED)
        self.assertTrue(clip.error.get("launch"))

    def test_doctor(self) -> None:
        result = run_doctor(sys.executable, str(FAKE_CORE))
        self.assertTrue(result.ok)
        report = result.last("doctor")
        self.assertTrue(report["ok"])
        self.assertEqual({c["id"] for c in report["checks"]}, {"gpu", "ffmpeg", "weights", "torch"})


if __name__ == "__main__":
    unittest.main()
