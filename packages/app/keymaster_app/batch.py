from __future__ import annotations

import threading
from typing import Callable

from keymaster_app.clips import ClipQueue
from keymaster_app.commands import KeyOptions, doctor_command, key_command
from keymaster_app.media import output_dir_for
from keymaster_app.runner import CoreProcess, RunResult

CLIP_STARTED = "clip_started"
CLIP_EVENT = "clip_event"
CLIP_FINISHED = "clip_finished"
BATCH_FINISHED = "batch_finished"

Notify = Callable[[str, "int | None"], None]


class Batch:
    def __init__(self, queue: ClipQueue, options: KeyOptions, python: str, core: str,
                 notify: Notify | None = None, env: dict[str, str] | None = None):
        self.queue = queue
        self.options = options
        self.python = python
        self.core = core
        self.notify = notify or (lambda kind, clip_id: None)
        self.env = env
        self._lock = threading.Lock()
        self._cancelled = False
        self._process: CoreProcess | None = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def start(self) -> None:
        self.queue.prepare_run()
        self._thread = threading.Thread(target=self._loop, name="keymaster-batch", daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            process = self._process
        if process:
            process.cancel()

    def join(self, timeout: float | None = None) -> bool:
        if self._thread:
            self._thread.join(timeout)
        return not self.running

    def _loop(self) -> None:
        try:
            while not self._cancelled:
                clip = self.queue.next_pending()
                if clip is None:
                    break
                with self.queue.lock:
                    clip.output_dir = output_dir_for(clip.path, self.options.output_root)
                    command = key_command(self.python, clip.path, clip.output_dir, self.options, clip.hint)
                clip_id = clip.id
                self.notify(CLIP_STARTED, clip_id)

                def on_event(event: dict, clip_id: int = clip_id) -> None:
                    self.queue.apply(clip_id, event)
                    self.notify(CLIP_EVENT, clip_id)

                process = CoreProcess(command, cwd=self.core, on_event=on_event, env=self.env)
                with self._lock:
                    self._process = process
                    if self._cancelled:
                        process.cancel()
                result = process.run()
                with self._lock:
                    self._process = None
                self.queue.finish(clip_id, result)
                self.notify(CLIP_FINISHED, clip_id)
        finally:
            self.notify(BATCH_FINISHED, None)


def run_doctor(python: str, core: str, env: dict[str, str] | None = None) -> RunResult:
    return CoreProcess(doctor_command(python), cwd=core, env=env).run()
