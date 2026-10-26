from __future__ import annotations

import collections
import os
import queue
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .events import RunState, parse_line

KILL_AFTER_SECONDS = 5.0
OUTPUT_KINDS = ("alpha", "fg", "cutout", "checker")
FORMATS = ("exr", "video")


@dataclass
class KeyOptions:
    input: str
    output_dir: str
    hint_first_frame: Optional[str] = None
    hint_quality: float = 0.95
    despill: float = 0.5
    format: str = "exr"
    outputs: Sequence[str] = field(default_factory=lambda: ("alpha", "fg", "cutout"))
    low_vram: bool = False
    frames: Optional[int] = None


def number(value: float) -> str:
    return f"{float(value):.4g}"


def key_command(python: str, options: KeyOptions) -> list[str]:
    argv = [python, "-m", "keymaster", "key", "--input", options.input, "--output-dir", options.output_dir]
    if options.hint_first_frame:
        argv += ["--hint-first-frame", options.hint_first_frame]
    argv += ["--hint-quality", number(options.hint_quality), "--despill", number(options.despill)]
    argv += ["--format", options.format if options.format in FORMATS else "exr"]
    outputs = [kind for kind in OUTPUT_KINDS if kind in options.outputs]
    if outputs:
        argv += ["--outputs", *outputs]
    if options.frames:
        argv += ["--frames", str(int(options.frames))]
    if options.low_vram:
        argv.append("--low-vram")
    argv.append("--json")
    return argv


def doctor_command(python: str) -> list[str]:
    return [python, "-m", "keymaster", "doctor", "--json"]


def child_env(base: Optional[dict] = None) -> dict:
    env = dict(os.environ if base is None else base)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


class CoreRun:
    def __init__(self, argv: Sequence[str], cwd: str, env: Optional[dict] = None):
        self.argv = list(argv)
        self.cwd = cwd
        self.env = child_env(env)
        self.state = RunState()
        self.process: Optional[subprocess.Popen] = None
        self.cancelled = False
        self.cancel_time: Optional[float] = None
        self._lines: "queue.Queue[Optional[str]]" = queue.Queue()
        self._stderr: collections.deque = collections.deque(maxlen=200)
        self._stdout_closed = False
        self._threads: list[threading.Thread] = []

    def start(self) -> "CoreRun":
        self.state.begin()
        try:
            self.process = subprocess.Popen(
                self.argv, cwd=self.cwd, env=self.env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                errors="replace", bufsize=1, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as exc:
            self.state.fail(message_key="blender.error.python_missing", params={"path": self.argv[0]}, detail=str(exc))
            return self
        self._threads = [
            threading.Thread(target=self._read_stdout, daemon=True),
            threading.Thread(target=self._read_stderr, daemon=True),
        ]
        for thread in self._threads:
            thread.start()
        return self

    def _read_stdout(self) -> None:
        assert self.process and self.process.stdout
        for line in self.process.stdout:
            self._lines.put(line)
        self._lines.put(None)

    def _read_stderr(self) -> None:
        assert self.process and self.process.stderr
        for line in self.process.stderr:
            self._stderr.append(line.rstrip("\n"))

    def stderr_tail(self, lines: int = 20) -> str:
        return "\n".join(list(self._stderr)[-lines:])

    def step(self) -> RunState:
        if self.state.finished or self.process is None:
            return self.state
        while True:
            try:
                line = self._lines.get_nowait()
            except queue.Empty:
                break
            if line is None:
                self._stdout_closed = True
                continue
            event = parse_line(line)
            if event is not None:
                self.state.apply(event)
        if self.cancelled and self.process.poll() is None and self.cancel_time is not None \
                and time.monotonic() - self.cancel_time > KILL_AFTER_SECONDS:
            self.process.kill()
        code = self.process.poll()
        if code is not None and self._stdout_closed:
            for thread in self._threads:
                thread.join(timeout=1.0)
            for stream in (self.process.stdout, self.process.stderr):
                if stream is not None:
                    stream.close()
            self.state.finish(code, cancelled=self.cancelled, detail=self.stderr_tail())
        return self.state

    def cancel(self) -> None:
        if self.process is None or self.state.finished:
            return
        self.cancelled = True
        self.cancel_time = time.monotonic()
        if self.process.poll() is None:
            self.process.terminate()

    def wait(self, timeout: float = 60.0, interval: float = 0.02) -> RunState:
        deadline = time.monotonic() + timeout
        while not self.step().finished:
            if time.monotonic() > deadline:
                raise TimeoutError("core run did not finish")
            time.sleep(interval)
        return self.state


def describe(argv: Sequence[str]) -> str:
    return subprocess.list2cmdline(argv) if sys.platform == "win32" else shlex.join(argv)


def run_dir_name(strip_name: str, stamp: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in strip_name).strip("_") or "strip"
    return f"{safe[:60]}_{stamp}"


def unique_dir(base: str, name: str) -> str:
    candidate = os.path.join(base, name)
    n = 2
    while os.path.exists(candidate):
        candidate = os.path.join(base, f"{name}-{n}")
        n += 1
    return candidate
