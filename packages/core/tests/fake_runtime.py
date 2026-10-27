from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

CALLS: list = []
FAIL = None
WINDOW_DELAY = 0.0
AUTO_CHUNK = 8


def reset():
    global FAIL, WINDOW_DELAY, AUTO_CHUNK
    CALLS.clear()
    FAIL = None
    WINDOW_DELAY = 0.0
    AUTO_CHUNK = 8


@dataclass
class InferenceConfig:
    hann_chunk: int = 80
    hann_stride: int = 40
    carry_hint: bool = True
    hint_quality: float = 0.95
    carry_hint_quality: float = 0.95
    shape_quantum: int = 128
    model_scale: float = 1.0
    num_frames: int = -1
    start_mode: str = "begin"
    seed: int = 0
    low_vram: bool = False
    auto_vram: bool = False
    stage2_batch: int = 1
    low_vram_foundation_chunk: int = 4
    outputs: set = field(default_factory=lambda: {"alpha", "fg"})
    temp_dir: Path = Path("/nonexistent")
    linear_brightness: float = 1.0
    linear_contrast: float = 1.0
    linear_contrast_pivot: float = 0.18
    frame_dir_fps: float = 24.0
    frame_dir_linear: bool = False
    cutout_linear: bool = False
    despill_strength: float = 0.5
    output_format: str = "video"
    exr_dtype: str = "half"


@dataclass
class WriterConfig:
    ffmpeg_bin: str = "ffmpeg"
    codec: str = "libx264"
    crf: int = 12
    preset: str = "medium"
    pix_fmt: str = "yuv444p10le"
    bitrate: str | None = None
    threads: int = 2


@dataclass
class RuntimePaths:
    package_root: Path

    @classmethod
    def from_package(cls, package_root, weights=None):
        return cls(Path(package_root))


def load_model(paths, device="cuda"):
    CALLS.append(("load_model", paths, device))
    print("Loading fake CorridorKey weights")
    return object()


def raw_clip_name(path) -> str:
    norm = os.path.normpath(str(path))
    name = os.path.splitext(os.path.basename(norm))[0]
    if name.lower() in {"input", "frames", "rgb"}:
        return os.path.basename(os.path.dirname(norm)) or name
    return name


def _meta(frames, width, height, fps, num_frames):
    n = frames if num_frames <= 0 else min(num_frames, frames)
    return {"native_fps": fps, "output_hw": (height, width), "shape_hw": (height, width), "num_frames": n}


def probe_video_meta(video_path, *, num_frames, **_):
    try:
        info = json.loads(Path(video_path).read_text())
    except (OSError, ValueError):
        raise RuntimeError(f"Could not open video: {video_path}")
    print(f"  probed {info['frames']} frames")
    meta = _meta(info["frames"], info["width"], info["height"], info["fps"], num_frames)
    meta["start_frame"] = 0
    return meta


def probe_frame_dir_meta(frame_dir, *, num_frames, fps, **_):
    paths = sorted(Path(frame_dir).glob("*.png"))
    if not paths:
        raise RuntimeError(f"No frames found under {frame_dir}")
    meta = _meta(len(paths), 64, 36, fps, num_frames)
    meta["frame_paths"] = [str(p) for p in paths][:meta["num_frames"]]
    return meta


def window_starts(T_all, chunk, stride):
    if T_all <= chunk:
        return [0]
    starts = list(range(0, T_all - chunk + 1, stride))
    if starts[-1] != T_all - chunk:
        starts.append(T_all - chunk)
    return starts


def iter_video_frame_chunks(source, meta, *, chunk_size, need_model):
    total = meta["num_frames"]
    for t0 in range(0, total, chunk_size):
        yield t0, None, [None] * min(chunk_size, total - t0)


def iter_frame_dir_chunks(source, meta, *, chunk_size, need_model):
    yield from iter_video_frame_chunks(source, meta, chunk_size=chunk_size, need_model=need_model)


def precompute_rvm_to_memmap(model, source, meta, rvm_path, *, chunk, reader_kind):
    Path(rvm_path).write_bytes(b"rvm")
    chunks = iter_video_frame_chunks if reader_kind == "video" else iter_frame_dir_chunks
    for _ in chunks(str(source), meta, chunk_size=chunk, need_model=False):
        pass


def precompute_foundations_to_memmap(model, source, meta, prefix, *, chunk, reader_kind):
    chunks = iter_video_frame_chunks if reader_kind == "video" else iter_frame_dir_chunks
    for _ in chunks(str(source), meta, chunk_size=chunk, need_model=False):
        pass
    return {}


class SequentialVideoWindowReader:
    def __init__(self, source, meta):
        self.source = source

    def window(self, t0, t1):
        return [None] * (t1 - t0), None, None

    def close(self):
        pass


class SequentialFrameDirWindowReader(SequentialVideoWindowReader):
    pass


class HintFrameDirReader:
    def __init__(self, path, meta):
        self.paths = sorted(str(p) for p in Path(path).glob("*.png"))
        if len(self.paths) < int(meta["num_frames"]):
            raise RuntimeError(f"{path}: only {len(self.paths)} hint frames")


class HintVideoReader:
    def __init__(self, path, meta):
        self.start_frame = int(meta.get("start_frame", 0))


def make_hint_reader(path, meta):
    if path is None:
        return None
    reader = HintFrameDirReader(path, meta) if os.path.isdir(path) else HintVideoReader(path, meta)
    CALLS.append(("hint_reader", reader))
    return reader


def hann_stage1_stream(model, source, meta, *, reader_cls, reader_kind, chunk, stride, baton_path,
                       on_baton_frames, full_hint_video_path=None, **_):
    total = meta["num_frames"]
    starts = window_starts(total, chunk, stride)
    make_hint_reader(full_hint_video_path, meta)
    reader = reader_cls(str(source), meta)
    flushed = 0
    try:
        for i, t0 in enumerate(starts):
            t1 = min(t0 + chunk, total)
            reader.window(t0, t1)
            if WINDOW_DELAY:
                time.sleep(WINDOW_DELAY)
            if FAIL is not None:
                raise FAIL
            next_start = starts[i + 1] if i + 1 < len(starts) else total
            if on_baton_frames is not None and next_start > flushed:
                on_baton_frames([(k, None, None) for k in range(flushed, next_start)])
                flushed = next_start
            print(f"      window {i + 1}/{len(starts)} [{t0}:{t1}]", flush=True)
    finally:
        reader.close()


class ExrSequenceWriter:
    def __init__(self, dir_path, fps, size, *, channels=3, dtype="half", maxsize=2, frame_name="frame"):
        self.dir_path = Path(dir_path)
        self.dir_path.mkdir(parents=True, exist_ok=True)
        self.frame_name = frame_name
        self.channels = channels
        self.frame_idx = 0

    def write_many(self, frames):
        for _ in frames:
            (self.dir_path / f"{self.frame_name}_{self.frame_idx:06d}.exr").write_bytes(b"exr")
            self.frame_idx += 1

    def release(self):
        pass


class ThreadedVideoWriter:
    def __init__(self, path, fps, size, cfg, *, maxsize=2, channels=3, color_trc=None):
        self.path = path
        self.channels = channels
        self.count = 0

    def write_many(self, frames):
        self.count += len(frames)

    def release(self):
        Path(self.path).write_bytes(b"v" * max(1, self.count))


def run_inference(model, input_path, output_dir, cfg, writer_cfg, *, initial_hint_path, hint_video_path):
    CALLS.append(("run_inference", {"input": input_path, "output_dir": output_dir, "cfg": cfg,
                                     "writer_cfg": writer_cfg, "initial_hint_path": initial_hint_path,
                                     "hint_video_path": hint_video_path}))
    cfg.temp_dir.mkdir(parents=True, exist_ok=True)
    is_dir = os.path.isdir(input_path)
    reader_kind = "frame_dir" if is_dir else "video"
    reader_cls = SequentialFrameDirWindowReader if is_dir else SequentialVideoWindowReader
    if is_dir:
        meta = probe_frame_dir_meta(input_path, num_frames=cfg.num_frames, fps=cfg.frame_dir_fps)
    else:
        meta = probe_video_meta(input_path, num_frames=cfg.num_frames)
    total = meta["num_frames"]
    if cfg.auto_vram:
        cfg.hann_chunk, cfg.hann_stride = AUTO_CHUNK, max(1, AUTO_CHUNK // 2)
    height, width = meta["output_hw"]
    clip = raw_clip_name(input_path)
    suffix = {"alpha": "alpha", "fg": "fg", "cutout": "cutout",
              "checker": f"checker_comp_despill{int(cfg.despill_strength * 100):03d}"}
    writers = {}
    try:
        for name in sorted(cfg.outputs):
            if cfg.output_format == "exr":
                writers[name] = ExrSequenceWriter(os.path.join(output_dir, f"{clip}_{suffix[name]}_exr"), 24.0,
                                                  (width, height), frame_name=suffix[name])
            else:
                ext = ".mov" if name == "cutout" else ".mp4"
                writers[name] = ThreadedVideoWriter(os.path.join(output_dir, f"{clip}_{suffix[name]}{ext}"), 24.0,
                                                    (width, height), writer_cfg)
        rvm_path = cfg.temp_dir / f"{clip}_rvm_feat.f16"
        precompute_rvm_to_memmap(model, input_path, meta, rvm_path, chunk=max(1, min(int(cfg.hann_chunk), 8)),
                                 reader_kind=reader_kind)
        if cfg.low_vram:
            precompute_foundations_to_memmap(model, input_path, meta, cfg.temp_dir / f"{clip}_foundation",
                                             chunk=4, reader_kind=reader_kind)

        def write_prediction_batches(items):
            for writer in writers.values():
                writer.write_many([None] * len(items))

        hann_stage1_stream(model, input_path, meta, reader_cls=reader_cls, reader_kind=reader_kind,
                           chunk=cfg.hann_chunk, stride=cfg.hann_stride, baton_path=cfg.temp_dir / "baton",
                           full_hint_video_path=hint_video_path,
                           on_baton_frames=None if cfg.low_vram else write_prediction_batches)
        if cfg.low_vram:
            for t0 in range(total):
                write_prediction_batches([(t0, None, None)])
    finally:
        for writer in writers.values():
            writer.release()
        rvm = cfg.temp_dir / f"{clip}_rvm_feat.f16"
        if rvm.exists():
            rvm.unlink()
    print(f"  wrote {len(writers)} output video(s) for {clip}")
