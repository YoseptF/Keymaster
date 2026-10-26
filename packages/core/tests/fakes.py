from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from keymaster import assets

from . import fake_runtime


class OutOfMemoryError(RuntimeError):
    pass


def make_torch(cuda: bool = True):
    torch = types.ModuleType("torch")
    torch.__version__ = "2.9.1+fake"
    torch.version = types.SimpleNamespace(cuda="12.8")
    torch.cuda = types.SimpleNamespace(
        is_available=lambda: cuda,
        get_device_name=lambda index=0: "Fake GPU",
        get_device_properties=lambda index=0: types.SimpleNamespace(total_memory=24 * 2**30),
        OutOfMemoryError=OutOfMemoryError,
    )
    return torch


def loader(cuda: bool = True):
    def load():
        return make_torch(cuda), fake_runtime
    return load


def make_upstream(root: Path, skip=()) -> Path:
    for asset in assets.ASSETS:
        if asset["id"] in skip:
            continue
        for options in asset["files"]:
            path = root / options[0]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"w")
    return root


def make_clip(path: Path, frames: int = 20, width: int = 64, height: int = 36, fps: float = 24.0) -> Path:
    path.write_text(json.dumps({"frames": frames, "width": width, "height": height, "fps": fps}))
    return path


def install_modules(cuda: bool = True):
    package = types.ModuleType("corridorkey")
    package.runtime = fake_runtime
    sys.modules["corridorkey"] = package
    sys.modules["corridorkey.runtime"] = fake_runtime
    sys.modules["torch"] = make_torch(cuda)
