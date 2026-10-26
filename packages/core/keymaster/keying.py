from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from . import assets, paths
from .errors import KeymasterError, classify
from .events import LineTap
from .progress import Tracker

OUTPUT_CHANNELS = {"alpha": 1, "fg": 3, "cutout": 4, "checker": 3}
TEMP_ROOT_NAME = "keymaster-core"


def import_upstream():
    paths.add_upstream_to_path(paths.UPSTREAM_DIR)
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    try:
        import torch
    except ImportError as exc:
        raise KeymasterError(message_key="core.error.dependency_missing", params={"name": "torch"},
                             detail=f"{type(exc).__name__}: {exc}") from exc
    try:
        from corridorkey import runtime
    except ImportError as exc:
        raise KeymasterError(message_key="core.error.dependency_missing", params={"name": exc.name or "corridorkey"},
                             detail=f"{type(exc).__name__}: {exc}") from exc
    return torch, runtime


def output_suffix(kind: str, despill: float) -> str:
    if kind == "checker":
        return f"checker_comp_despill{int(despill * 100):03d}"
    return kind


def unique(values):
    seen = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def make_temp_dir(base: Path | None = None) -> Path:
    root = Path(base or tempfile.gettempdir()) / TEMP_ROOT_NAME
    root.mkdir(parents=True, exist_ok=True)
    for stale in root.glob("run-*"):
        try:
            pid = int(stale.name.split("-", 1)[1])
        except ValueError:
            continue
        if pid != os.getpid() and not pid_alive(pid):
            shutil.rmtree(stale, ignore_errors=True)
    run = root / f"run-{os.getpid()}"
    shutil.rmtree(run, ignore_errors=True)
    run.mkdir()
    return run


def preflight(args) -> None:
    source = Path(args.input)
    if not source.exists():
        raise KeymasterError(message_key="core.error.input_unreadable", params={"path": args.input},
                             detail=f"input not found: {args.input}")
    for hint in (args.hint_first_frame, args.hint_video):
        if hint and not Path(hint).exists():
            raise KeymasterError(message_key="core.error.input_unreadable", params={"path": hint},
                                 detail=f"hint not found: {hint}")
    for name, value in (("despill", args.despill), ("hint-quality", args.hint_quality)):
        if not 0.0 <= value <= 1.0:
            raise KeymasterError(message_key="core.error.invalid_arguments", params={"problem": f"--{name} {value}"},
                                 detail=f"--{name} must be between 0 and 1")
    out = Path(args.output_dir)
    try:
        out.mkdir(parents=True, exist_ok=True)
        probe = out / f".keymaster-write-test-{os.getpid()}"
        probe.write_bytes(b"")
        probe.unlink()
    except OSError as exc:
        raise KeymasterError(message_key="core.error.output_unwritable", params={"path": args.output_dir},
                             detail=f"{type(exc).__name__}: {exc}") from exc
    if args.format == "video" and shutil.which("ffmpeg") is None:
        raise KeymasterError(message_key="core.error.ffmpeg_missing", detail="ffmpeg is not on PATH")
    lacking = assets.missing(paths.UPSTREAM_DIR)
    if lacking:
        raise KeymasterError(message_key="core.error.weights_missing", params={"missing": ", ".join(lacking)},
                             detail=f"missing assets under {paths.UPSTREAM_DIR}: {', '.join(lacking)}")


def build_configs(rt, args, temp_dir: Path):
    auto_vram = not args.low_vram
    infer_cfg = rt.InferenceConfig(
        hann_chunk=80,
        hann_stride=40,
        auto_vram=auto_vram,
        low_vram=bool(args.low_vram),
        hint_quality=float(args.hint_quality),
        num_frames=args.frames if args.frames and args.frames > 0 else -1,
        outputs=set(args.outputs),
        temp_dir=temp_dir,
        despill_strength=float(args.despill),
        output_format=args.format,
        exr_dtype="half",
    )
    writer_cfg = rt.WriterConfig()
    return infer_cfg, writer_cfg


def probe(rt, args, infer_cfg) -> dict:
    try:
        if os.path.isdir(args.input):
            meta = rt.probe_frame_dir_meta(
                args.input, num_frames=infer_cfg.num_frames, shape_quantum=infer_cfg.shape_quantum,
                fps=infer_cfg.frame_dir_fps, exr_linear=infer_cfg.frame_dir_linear,
                model_scale=infer_cfg.model_scale)
        else:
            meta = rt.probe_video_meta(
                args.input, num_frames=infer_cfg.num_frames, shape_quantum=infer_cfg.shape_quantum,
                native_resolution=True, start_mode=infer_cfg.start_mode, seed=infer_cfg.seed,
                model_scale=infer_cfg.model_scale, linear_brightness=infer_cfg.linear_brightness,
                linear_contrast=infer_cfg.linear_contrast,
                linear_contrast_pivot=infer_cfg.linear_contrast_pivot)
    except Exception as exc:
        raise KeymasterError(message_key="core.error.input_unreadable", params={"path": args.input},
                             detail=f"{type(exc).__name__}: {exc}") from exc
    if int(meta.get("num_frames", 0)) <= 0 or min(meta["output_hw"]) <= 0:
        raise KeymasterError(message_key="core.error.input_unreadable", params={"path": args.input},
                             detail=f"no decodable frames in {args.input}")
    return meta


@contextmanager
def patched(target, name: str, value):
    original = getattr(target, name)
    setattr(target, name, value)
    try:
        yield original
    finally:
        setattr(target, name, original)


@contextmanager
def instrument(rt, tracker: Tracker, infer_cfg, total_frames: int):
    state = {"pass": 0, "passes": 1, "windows": 1, "started": 0, "written": {}, "releasing": False}

    def chunk_wrapper(original):
        def wrapper(*a, **kw):
            for item in original(*a, **kw):
                done = item[0] + len(item[2])
                local = (state["pass"] + min(1.0, done / max(1, total_frames))) / state["passes"]
                tracker.update("prepass", local)
                yield item
        return wrapper

    def pass_wrapper(original, index):
        def wrapper(*a, **kw):
            state["passes"] = 2 if infer_cfg.low_vram else 1
            state["pass"] = index
            tracker.update("prepass", index / state["passes"])
            result = original(*a, **kw)
            tracker.update("prepass", (index + 1) / state["passes"])
            return result
        return wrapper

    def stage1_wrapper(original):
        def wrapper(model, source, meta, **kw):
            tracker.update("prepass", 1.0)
            state["windows"] = max(1, len(rt.window_starts(int(meta["num_frames"]), kw["chunk"], kw["stride"])))
            tracker.update("stage1", 0.0)
            reader_cls = kw.get("reader_cls")
            if reader_cls is not None:
                class CountedReader(reader_cls):
                    def window(self, t0, t1):
                        state["started"] += 1
                        return super().window(t0, t1)

                kw["reader_cls"] = CountedReader
            result = original(model, source, meta, **kw)
            tracker.update("stage1", 1.0)
            return result
        return wrapper

    def on_window(match):
        tracker.update("stage1", int(match.group(1)) / max(1, int(match.group(2))))

    def writer_wrapper(original):
        class Counted(original):
            def write_many(self, frames):
                result = super().write_many(frames)
                state["written"][id(self)] = state["written"].get(id(self), 0) + len(frames)
                if state["started"]:
                    tracker.update("stage1", state["started"] / state["windows"])
                tracker.update("stage2", min(state["written"].values()) / max(1, total_frames))
                return result

            def release(self):
                if not state["releasing"]:
                    state["releasing"] = True
                    tracker.update("stage2", 1.0)
                    tracker.update("write", 0.0)
                return super().release()

        Counted.__name__ = original.__name__
        return Counted

    tap = LineTap(sys.stdout, [(r"window (\d+)/(\d+)", on_window)])
    previous_stdout = sys.stdout
    sys.stdout = tap
    names = (
        ("iter_video_frame_chunks", chunk_wrapper),
        ("iter_frame_dir_chunks", chunk_wrapper),
        ("precompute_rvm_to_memmap", lambda f: pass_wrapper(f, 0)),
        ("precompute_foundations_to_memmap", lambda f: pass_wrapper(f, 1)),
        ("hann_stage1_stream", stage1_wrapper),
        ("ExrSequenceWriter", writer_wrapper),
        ("ThreadedVideoWriter", writer_wrapper),
    )
    originals = {name: getattr(rt, name) for name, _ in names}
    try:
        for name, wrap in names:
            setattr(rt, name, wrap(originals[name]))
        yield state
    finally:
        for name, original in originals.items():
            setattr(rt, name, original)
        tap.flush()
        sys.stdout = previous_stdout


def collect_outputs(rt, args, total_frames: int) -> list[dict]:
    out_dir = Path(args.output_dir).resolve()
    clip = rt.raw_clip_name(args.input)
    items = []
    for kind in unique(args.outputs):
        suffix = output_suffix(kind, args.despill)
        if args.format == "exr":
            seq = out_dir / f"{clip}_{suffix}_exr"
            first = seq / f"{suffix}_{0:06d}.exr"
            last = seq / f"{suffix}_{total_frames - 1:06d}.exr"
            if not (first.is_file() and last.is_file()):
                raise KeymasterError(message_key="core.error.unknown",
                                     detail=f"expected {first} .. {last} after keying")
            items.append({"event": "output", "kind": kind, "type": "image_sequence", "path": str(seq),
                          "pattern": str(seq / f"{suffix}_%06d.exr"), "first_frame": 0, "frames": total_frames})
        else:
            ext = ".mov" if kind == "cutout" else ".mp4"
            path = out_dir / f"{clip}_{suffix}{ext}"
            if not path.is_file() or path.stat().st_size == 0:
                raise KeymasterError(message_key="core.error.encode_failed", detail=f"expected {path} after keying")
            items.append({"event": "output", "kind": kind, "type": "video", "path": str(path),
                          "first_frame": 0, "frames": total_frames})
    return items


def run_key(args, emit, upstream_loader=None, temp_base: Path | None = None) -> dict:
    started = time.monotonic()
    args.input = os.path.abspath(args.input)
    args.output_dir = os.path.abspath(args.output_dir)
    args.outputs = unique(args.outputs)
    preflight(args)
    torch, rt = (upstream_loader or import_upstream)()
    if not torch.cuda.is_available():
        raise KeymasterError(message_key="core.error.no_gpu", detail="torch.cuda.is_available() is False")
    temp_dir = make_temp_dir(temp_base)
    try:
        infer_cfg, writer_cfg = build_configs(rt, args, temp_dir)
        meta = probe(rt, args, infer_cfg)
        total = int(meta["num_frames"])
        height, width = (int(v) for v in meta["output_hw"])
        emit({"event": "start", "input": args.input, "frames": total, "width": width, "height": height,
              "fps": round(float(meta["native_fps"]), 3)})
        tracker = Tracker(emit)
        tracker.update("load", 0.0)
        runtime_paths = rt.RuntimePaths.from_package(paths.UPSTREAM_DIR)
        model = rt.load_model(runtime_paths, device="cuda")
        tracker.update("load", 1.0)
        with instrument(rt, tracker, infer_cfg, total):
            rt.run_inference(model, args.input, args.output_dir, infer_cfg, writer_cfg,
                             initial_hint_path=args.hint_first_frame, hint_video_path=args.hint_video)
        outputs = collect_outputs(rt, args, total)
        tracker.finish("write")
        for item in outputs:
            emit(item)
        done = {"event": "done", "outputs": outputs, "seconds": round(time.monotonic() - started, 1)}
        emit(done)
        return done
    except BaseException as exc:
        error = classify(exc)
        if error.message_key == "core.error.input_unreadable" and not error.params.get("path"):
            error.params["path"] = args.input
        if error.message_key == "core.error.weights_missing" and not error.params.get("missing"):
            error.params["missing"] = ", ".join(assets.missing(paths.UPSTREAM_DIR)) or "-"
        if error is exc:
            raise
        raise error from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
