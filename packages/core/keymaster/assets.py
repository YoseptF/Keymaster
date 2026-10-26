from __future__ import annotations

import importlib.util
import os
import sys
import threading
import time
from pathlib import Path

from . import paths, settings
from .errors import KeymasterError
from .progress import Tracker

ASSETS = (
    {"id": "corridorkey", "dir": "weights", "bytes": 2_661_717_584,
     "files": (("weights/corridorkey_v2.safetensors", "weights/corridorkey_v2.pt"),
               ("weights/foundation_stats.safetensors", "weights/foundation_stats.pt")),
     "message_key": "core.progress.download_corridorkey"},
    {"id": "cradio", "dir": "vfms/cradio", "bytes": 1_725_512_023,
     "files": (("vfms/cradio/C-RADIOv4-SO400M/model.safetensors",),
               ("vfms/cradio/C-RADIOv4-SO400M/config.json",)),
     "message_key": "core.progress.download_cradio"},
    {"id": "moge", "dir": "vfms/moge", "bytes": 419_110_160,
     "files": (("vfms/moge/model.pt",),),
     "message_key": "core.progress.download_moge"},
    {"id": "rvm", "dir": "vfms/rvm", "bytes": 270_086_372,
     "files": (("vfms/rvm/pretrain_rvm_small16_256_204031069.npz",),),
     "message_key": "core.progress.download_rvm"},
)


def present(asset: dict, root: Path) -> bool:
    return all(any((root / option).is_file() for option in options) for options in asset["files"])


def missing(root: Path | None = None) -> list[str]:
    root = root or paths.UPSTREAM_DIR
    return [asset["id"] for asset in ASSETS if not present(asset, root)]


def tree_bytes(path: Path) -> int:
    total = 0
    for base, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(base, name)).st_size
            except OSError:
                pass
    return total


def load_downloader(root: Path):
    script = root / "scripts" / "download_weights.py"
    spec = importlib.util.spec_from_file_location("keymaster_download_weights", script)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as exc:
        raise KeymasterError(message_key="core.error.dependency_missing", params={"name": exc.name or ""},
                             detail=str(exc)) from exc
    return module


def fetch(module, asset_id: str, root: Path) -> None:
    if asset_id == "corridorkey":
        module.download_corridorkey(root, module.CORRIDORKEY_REPO, None)
    elif asset_id == "cradio":
        module.download_cradio(root)
    elif asset_id == "moge":
        module.download_moge(root)
    else:
        module.download_rvm(root)


def run_setup(emit, root: Path | None = None, downloader=None, poll: float = 0.5) -> dict:
    root = root or paths.UPSTREAM_DIR
    started = time.monotonic()
    todo = [asset for asset in ASSETS if not present(asset, root)]
    phases = {a["id"]: {"weight": a["bytes"], "message_key": a["message_key"]} for a in todo}
    phases["done"] = {"weight": 1, "message_key": "core.progress.download_done"}

    def send(obj):
        if obj["event"] == "progress":
            obj["phase"] = "download"
        emit(obj)

    tracker = Tracker(send, phases)
    module = downloader if downloader is not None or not todo else load_downloader(root)
    for asset in todo:
        target = root / asset["dir"]
        target.mkdir(parents=True, exist_ok=True)
        base = tree_bytes(target)
        tracker.update(asset["id"], 0.0, force=True)
        stop = threading.Event()

        def watch(asset=asset, target=target, base=base, stop=stop):
            while not stop.wait(poll):
                tracker.update(asset["id"], (tree_bytes(target) - base) / asset["bytes"])

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        try:
            fetch(module, asset["id"], root)
        except KeymasterError:
            raise
        except Exception as exc:
            raise KeymasterError(message_key="core.error.download_failed", params={"asset": asset["id"]},
                                 detail=f"{type(exc).__name__}: {exc}") from exc
        finally:
            stop.set()
            watcher.join()
        if not present(asset, root):
            raise KeymasterError(message_key="core.error.download_failed", params={"asset": asset["id"]},
                                 detail=f"{asset['id']} is still missing after download")
        tracker.update(asset["id"], 1.0)
    tracker.finish("done")
    saved = settings.update({"python": os.path.abspath(sys.executable), "core": str(paths.CORE_DIR)})
    emit({"event": "done", "outputs": [], "seconds": round(time.monotonic() - started, 1)})
    return saved
