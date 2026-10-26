from __future__ import annotations

import threading

PHASES = {
    "load": {"weight": 0.10, "message_key": "core.progress.load"},
    "prepass": {"weight": 0.15, "message_key": "core.progress.prepass"},
    "stage1": {"weight": 0.35, "message_key": "core.progress.stage1"},
    "stage2": {"weight": 0.35, "message_key": "core.progress.stage2"},
    "write": {"weight": 0.05, "message_key": "core.progress.write"},
}
STEP = 0.005


class Tracker:
    def __init__(self, emit, phases=None):
        self.emit = emit
        self.phases = phases or PHASES
        self.local = {name: 0.0 for name in self.phases}
        self.fraction = 0.0
        self.sent = -1.0
        self.seen: set[str] = set()
        self.lock = threading.Lock()

    def overall(self) -> float:
        total = sum(p["weight"] for p in self.phases.values())
        return sum(self.phases[name]["weight"] * value for name, value in self.local.items()) / total

    def update(self, phase: str, value: float, force: bool = False) -> None:
        with self.lock:
            value = min(1.0, max(0.0, float(value)))
            self.local[phase] = max(self.local[phase], value)
            self.fraction = max(self.fraction, min(1.0, self.overall()))
            first = phase not in self.seen
            if not (force or first or self.fraction - self.sent >= STEP):
                return
            self.seen.add(phase)
            self.sent = self.fraction
            self.emit({"event": "progress", "phase": phase, "fraction": round(self.fraction, 4),
                       "message_key": self.phases[phase]["message_key"]})

    def finish(self, phase: str) -> None:
        with self.lock:
            for name in self.phases:
                self.local[name] = 1.0
            self.fraction = 1.0
        self.update(phase, 1.0, force=True)
