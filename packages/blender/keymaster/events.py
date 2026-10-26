from __future__ import annotations

import json
from typing import Optional

IDLE = "idle"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"
FINISHED = (DONE, FAILED, CANCELLED)
CANCEL_EXIT = 130


def parse_line(line: str) -> Optional[dict]:
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        event = json.loads(line)
    except ValueError:
        return None
    if not isinstance(event, dict) or not isinstance(event.get("event"), str):
        return None
    return event


class RunState:
    def __init__(self) -> None:
        self.status = IDLE
        self.fraction = 0.0
        self.message_key: Optional[str] = None
        self.start: Optional[dict] = None
        self.outputs: list[dict] = []
        self.done: Optional[dict] = None
        self.error: Optional[dict] = None
        self.doctor: Optional[dict] = None
        self.returncode: Optional[int] = None

    @property
    def finished(self) -> bool:
        return self.status in FINISHED

    def begin(self) -> None:
        self.status = RUNNING

    def apply(self, event: dict) -> None:
        kind = event.get("event")
        if kind == "start":
            self.start = event
        elif kind == "progress":
            try:
                fraction = float(event.get("fraction", self.fraction))
            except (TypeError, ValueError):
                fraction = self.fraction
            self.fraction = min(1.0, max(self.fraction, fraction))
            if event.get("message_key"):
                self.message_key = event["message_key"]
        elif kind == "output":
            self.outputs.append(event)
        elif kind == "done":
            self.done = event
            self.fraction = 1.0
        elif kind == "error":
            self.error = {"message_key": event.get("message_key"), "params": event.get("params") or {},
                          "detail": event.get("detail") or ""}
        elif kind == "doctor":
            self.doctor = event

    def fail(self, message_key: str, params: Optional[dict] = None, detail: str = "") -> None:
        self.error = {"message_key": message_key, "params": params or {}, "detail": detail}
        self.status = FAILED

    def finish(self, returncode: int, cancelled: bool = False, detail: str = "") -> None:
        self.returncode = returncode
        if cancelled or returncode == CANCEL_EXIT:
            self.status = CANCELLED
        elif returncode == 0 and self.error is None:
            self.status = DONE
        else:
            if self.error is None:
                self.error = {"message_key": None, "params": {"code": returncode}, "detail": detail}
            self.status = FAILED

    def final_outputs(self) -> list[dict]:
        if self.done and isinstance(self.done.get("outputs"), list) and self.done["outputs"]:
            return self.done["outputs"]
        return self.outputs
