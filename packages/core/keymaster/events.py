from __future__ import annotations

import io
import json
import os
import re
import sys
import threading

from .i18n import t


class Emitter:
    def __init__(self, json_mode: bool, stream=None, human=None, lang: str | None = None):
        self.json_mode = json_mode
        self.stream = stream if stream is not None else sys.stdout
        self.human = human if human is not None else sys.stderr
        self.lang = lang
        self.lock = threading.Lock()
        self.broken = False
        self.last_line = None
        self.history: list[dict] = []

    def emit(self, obj: dict) -> None:
        with self.lock:
            self.history.append(obj)
            if self.json_mode:
                self._write(self.stream, json.dumps(obj, ensure_ascii=False))
            else:
                for line in self.render(obj):
                    if line != self.last_line:
                        self.last_line = line
                        self._write(self.human, line)

    def _write(self, stream, line: str) -> None:
        if self.broken:
            return
        try:
            stream.write(line + "\n")
            stream.flush()
        except (BrokenPipeError, OSError, ValueError):
            self.broken = True

    def render(self, obj: dict) -> list[str]:
        lang = self.lang
        kind = obj.get("event")
        if kind == "progress":
            return [f"[{int(obj['fraction'] * 100):3d}%] {t(obj['message_key'], obj.get('params'), lang)}"]
        if kind == "start":
            return [t("core.cli.start", obj, lang)]
        if kind == "output":
            return [t("core.cli.output", obj, lang)]
        if kind == "done":
            return [t("core.cli.done", obj, lang)]
        if kind == "error":
            return [t(obj["message_key"], obj.get("params"), lang), obj.get("detail", "")]
        if kind == "doctor":
            lines = [("OK  " if c["ok"] else "--  ") + t(c["message_key"], c.get("params"), lang) for c in obj["checks"]]
            lines.append(t("core.cli.doctor_ok", None, lang) if obj["ok"] else t("core.cli.doctor_failed", None, lang))
            return lines
        return [json.dumps(obj, ensure_ascii=False)]


class LineTap(io.TextIOBase):
    def __init__(self, target, patterns=()):
        self.target = target
        self.patterns = list(patterns)
        self.pending = ""

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        try:
            self.target.write(text)
        except (OSError, ValueError):
            pass
        self.pending += text
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            self.scan(line)
        return len(text)

    def scan(self, line: str) -> None:
        for pattern, callback in self.patterns:
            match = re.search(pattern, line)
            if match:
                callback(match)

    def flush(self) -> None:
        try:
            self.target.flush()
        except (OSError, ValueError):
            pass

    def fileno(self) -> int:
        return self.target.fileno()


def claim_stdout():
    sys.stdout.flush()
    events = os.fdopen(os.dup(1), "w", encoding="utf-8", newline="\n")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return events
