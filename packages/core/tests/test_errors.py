from __future__ import annotations

import errno
import unittest

from keymaster.errors import Cancelled, KeymasterError, classify

from .fakes import OutOfMemoryError


class ClassifyTest(unittest.TestCase):
    def check(self, exc, key):
        self.assertEqual(classify(exc).message_key, key)

    def test_mapping(self):
        self.check(OutOfMemoryError("CUDA out of memory. Tried to allocate 2 GiB"), "core.error.out_of_memory")
        self.check(RuntimeError("CUDA error: out of memory"), "core.error.out_of_memory")
        self.check(FileNotFoundError("ffmpeg binary not found: ffmpeg. Install ffmpeg"), "core.error.ffmpeg_missing")
        self.check(RuntimeError("ffmpeg writer failed with exit code 1: x.mp4"), "core.error.encode_failed")
        self.check(FileNotFoundError("missing runtime asset(s): /w"), "core.error.weights_missing")
        self.check(RuntimeError("CorridorKey v2 runtime requires a CUDA GPU."), "core.error.no_gpu")
        self.check(RuntimeError("Found no NVIDIA driver on your system."), "core.error.no_gpu")
        self.check(RuntimeError("Could not open video: a.mp4"), "core.error.input_unreadable")
        self.check(RuntimeError("No frames found under /x"), "core.error.input_unreadable")
        self.check(OSError(errno.ENOSPC, "No space left on device"), "core.error.disk_full")
        self.check(ModuleNotFoundError("No module named 'cv2'", name="cv2"), "core.error.dependency_missing")
        self.check(Cancelled(), "core.error.cancelled")
        self.check(KeyboardInterrupt(), "core.error.cancelled")
        self.check(ValueError("something else"), "core.error.unknown")

    def test_keeps_detail(self):
        error = classify(ValueError("boom"))
        self.assertEqual(error.event(), {"event": "error", "message_key": "core.error.unknown", "params": {},
                                         "detail": "ValueError: boom"})

    def test_passthrough(self):
        error = KeymasterError(message_key="core.error.no_gpu")
        self.assertIs(classify(error), error)
