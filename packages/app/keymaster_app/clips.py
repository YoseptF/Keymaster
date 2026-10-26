from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

from keymaster_app.runner import RunResult

QUEUED = "queued"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"


@dataclass
class Clip:
    id: int
    path: str
    hint: str | None = None
    status: str = QUEUED
    progress: float = 0.0
    phase: str = ""
    message_key: str = ""
    params: dict = field(default_factory=dict)
    error: dict | None = None
    outputs: list[dict] = field(default_factory=list)
    output_dir: str | None = None
    frames: int | None = None
    seconds: float | None = None

    @property
    def name(self) -> str:
        return Path(self.path).name or self.path

    @property
    def finished(self) -> bool:
        return self.status in (DONE, FAILED, CANCELLED)

    def reset(self) -> None:
        self.status = QUEUED
        self.progress = 0.0
        self.phase = ""
        self.message_key = ""
        self.params = {}
        self.error = None
        self.outputs = []
        self.frames = None
        self.seconds = None


class ClipQueue:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.clips: list[Clip] = []
        self._next_id = 1

    def __len__(self) -> int:
        return len(self.clips)

    def get(self, clip_id: int) -> Clip | None:
        with self.lock:
            return next((c for c in self.clips if c.id == clip_id), None)

    def add(self, paths: list[str]) -> list[Clip]:
        added = []
        with self.lock:
            known = {os.path.normcase(c.path) for c in self.clips}
            for raw in paths:
                path = os.path.abspath(raw)
                if os.path.normcase(path) in known:
                    continue
                known.add(os.path.normcase(path))
                clip = Clip(id=self._next_id, path=path)
                self._next_id += 1
                self.clips.append(clip)
                added.append(clip)
        return added

    def remove(self, ids: list[int]) -> list[int]:
        with self.lock:
            gone = [c.id for c in self.clips if c.id in ids and c.status != RUNNING]
            self.clips = [c for c in self.clips if c.id not in gone]
            return gone

    def clear_finished(self) -> list[int]:
        with self.lock:
            return self.remove([c.id for c in self.clips if c.status == DONE])

    def set_hint(self, clip_id: int, hint: str | None) -> bool:
        with self.lock:
            clip = self.get(clip_id)
            if not clip or clip.status == RUNNING:
                return False
            clip.hint = os.path.abspath(hint) if hint else None
            return True

    def prepare_run(self) -> int:
        with self.lock:
            for clip in self.clips:
                if clip.status in (FAILED, CANCELLED):
                    clip.reset()
            return sum(1 for c in self.clips if c.status == QUEUED)

    def next_pending(self) -> Clip | None:
        with self.lock:
            for clip in self.clips:
                if clip.status == QUEUED:
                    clip.reset()
                    clip.status = RUNNING
                    return clip
        return None

    def apply(self, clip_id: int, event: dict) -> None:
        with self.lock:
            clip = self.get(clip_id)
            if not clip:
                return
            kind = event.get("event")
            if kind == "start":
                frames = event.get("frames")
                clip.frames = frames if isinstance(frames, int) else None
            elif kind == "progress":
                try:
                    fraction = float(event.get("fraction", clip.progress))
                except (TypeError, ValueError):
                    fraction = clip.progress
                clip.progress = max(clip.progress, min(1.0, max(0.0, fraction)))
                clip.phase = str(event.get("phase", ""))
                clip.message_key = str(event.get("message_key", ""))
                clip.params = event.get("params") if isinstance(event.get("params"), dict) else {}
            elif kind == "output":
                clip.outputs.append(event)
            elif kind == "done":
                outputs = event.get("outputs")
                if isinstance(outputs, list) and outputs:
                    clip.outputs = [o for o in outputs if isinstance(o, dict)]
                seconds = event.get("seconds")
                clip.seconds = float(seconds) if isinstance(seconds, (int, float)) else None
            elif kind == "error":
                clip.error = {
                    "message_key": str(event.get("message_key", "")),
                    "params": event.get("params") if isinstance(event.get("params"), dict) else {},
                    "detail": str(event.get("detail", "")),
                }

    def finish(self, clip_id: int, result: RunResult) -> None:
        with self.lock:
            clip = self.get(clip_id)
            if not clip:
                return
            if result.code == 0 and result.last("done") is not None:
                clip.status = DONE
                clip.progress = 1.0
                clip.error = None
            elif result.cancelled:
                clip.status = CANCELLED
            else:
                clip.status = FAILED
                if result.launch_error:
                    clip.error = {"message_key": "", "params": {}, "detail": result.launch_error, "launch": True}
                elif clip.error is None:
                    clip.error = {"message_key": "", "params": {}, "detail": result.stderr_tail.strip(), "code": result.code}

    def overall(self) -> float:
        with self.lock:
            if not self.clips:
                return 0.0
            total = sum(1.0 if c.status == DONE else c.progress if c.status == RUNNING else 0.0 for c in self.clips)
            return total / len(self.clips)

    def counts(self) -> dict[str, int]:
        with self.lock:
            counts = {QUEUED: 0, RUNNING: 0, DONE: 0, FAILED: 0, CANCELLED: 0}
            for clip in self.clips:
                counts[clip.status] = counts.get(clip.status, 0) + 1
            return counts
