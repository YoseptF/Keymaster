from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

CANCELLED_EXIT = 130


def parse_event(line: str) -> dict | None:
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        event = json.loads(line)
    except ValueError:
        return None
    if isinstance(event, dict) and isinstance(event.get("event"), str):
        return event
    return None


@dataclass
class RunResult:
    code: int | None
    cancelled: bool
    events: list[dict] = field(default_factory=list)
    stderr_tail: str = ""
    launch_error: str | None = None

    def last(self, kind: str) -> dict | None:
        for event in reversed(self.events):
            if event.get("event") == kind:
                return event
        return None

    @property
    def ok(self) -> bool:
        return not self.cancelled and self.code == 0 and self.launch_error is None


class CoreProcess:
    def __init__(self, command: list[str], cwd: str, on_event: Callable[[dict], None] | None = None,
                 env: dict[str, str] | None = None):
        self.command = command
        self.cwd = cwd
        self.on_event = on_event
        self.env = env
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def _environment(self) -> dict[str, str]:
        env = dict(os.environ if self.env is None else self.env)
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def run(self) -> RunResult:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        with self._lock:
            if self._cancelled:
                return RunResult(code=None, cancelled=True)
            try:
                self._proc = subprocess.Popen(
                    self.command, cwd=self.cwd, env=self._environment(),
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    encoding="utf-8", errors="replace", bufsize=1, creationflags=flags)
            except OSError as exc:
                return RunResult(code=None, cancelled=False, launch_error=str(exc))
            proc = self._proc
        tail: deque[str] = deque(maxlen=200)
        drain = threading.Thread(target=lambda: tail.extend(proc.stderr), daemon=True)
        drain.start()
        events: list[dict] = []
        for line in proc.stdout:
            event = parse_event(line)
            if event is None:
                continue
            events.append(event)
            if self.on_event:
                self.on_event(event)
        code = proc.wait()
        drain.join(timeout=5)
        for stream in (proc.stdout, proc.stderr):
            try:
                stream.close()
            except OSError:
                pass
        cancelled = self._cancelled or code == CANCELLED_EXIT
        return RunResult(code=code, cancelled=cancelled, events=events, stderr_tail="".join(tail)[-4000:])
