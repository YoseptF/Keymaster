from __future__ import annotations

import errno


class KeymasterError(Exception):
    def __init__(self, message_key: str, params: dict | None = None, detail: str = ""):
        super().__init__(detail or message_key)
        self.message_key = message_key
        self.params = params or {}
        self.detail = detail or message_key

    def event(self) -> dict:
        return {"event": "error", "message_key": self.message_key, "params": self.params, "detail": self.detail}


class Cancelled(BaseException):
    pass


INPUT_PROBLEMS = (
    "could not open video",
    "could not open hint video",
    "no frames found under",
    "no hint frame found",
    "hint frame decode failed",
    "hint pad",
    "hint video",
    "frame decode failed",
    "failed to read frame",
)
NO_GPU_PROBLEMS = (
    "requires a cuda gpu",
    "found no nvidia driver",
    "no cuda gpus are available",
    "torch not compiled with cuda",
    "cuda driver version is insufficient",
)


def classify(exc: BaseException) -> KeymasterError:
    if isinstance(exc, KeymasterError):
        return exc
    if isinstance(exc, (Cancelled, KeyboardInterrupt)):
        return KeymasterError(message_key="core.error.cancelled", detail="cancelled")
    detail = f"{type(exc).__name__}: {exc}"
    text = detail.lower()
    if "outofmemory" in type(exc).__name__.lower() or "out of memory" in text:
        return KeymasterError(message_key="core.error.out_of_memory", detail=detail)
    if "ffmpeg binary not found" in text:
        return KeymasterError(message_key="core.error.ffmpeg_missing", detail=detail)
    if "ffmpeg writer failed" in text or isinstance(exc, BrokenPipeError):
        return KeymasterError(message_key="core.error.encode_failed", detail=detail)
    if "missing runtime asset" in text:
        return KeymasterError(message_key="core.error.weights_missing", params={"missing": ""}, detail=detail)
    if any(p in text for p in NO_GPU_PROBLEMS):
        return KeymasterError(message_key="core.error.no_gpu", detail=detail)
    if any(p in text for p in INPUT_PROBLEMS):
        return KeymasterError(message_key="core.error.input_unreadable", params={"path": ""}, detail=detail)
    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
        return KeymasterError(message_key="core.error.disk_full", detail=detail)
    if isinstance(exc, ModuleNotFoundError):
        return KeymasterError(message_key="core.error.dependency_missing", params={"name": exc.name or ""}, detail=detail)
    return KeymasterError(message_key="core.error.unknown", detail=detail)
