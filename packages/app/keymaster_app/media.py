from __future__ import annotations

import os
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mxf", ".m4v", ".mpg", ".mpeg", ".wmv", ".mts", ".m2ts"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".exr", ".tif", ".tiff", ".dpx", ".bmp", ".webp", ".tga"}
HINT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".exr", ".tif", ".tiff", ".bmp", ".webp", ".tga"}
PREVIEW_ORDER = ("cutout", "checker", "fg", "alpha")


def is_video(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS


def is_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def has_frames(directory: Path) -> bool:
    try:
        return any(is_image(p) for p in directory.iterdir())
    except OSError:
        return False


def collect_inputs(paths: list[str]) -> tuple[list[str], list[str]]:
    found: list[str] = []
    skipped: list[str] = []
    for raw in paths:
        path = Path(os.path.abspath(raw))
        if path.is_dir():
            if has_frames(path):
                found.append(str(path))
                continue
            videos = sorted(p for p in path.iterdir() if is_video(p))
            if videos:
                found.extend(str(p) for p in videos)
            else:
                skipped.append(str(path))
        elif is_video(path):
            found.append(str(path))
        elif is_image(path):
            found.append(str(path.parent))
        else:
            skipped.append(str(path))
    return list(dict.fromkeys(found)), skipped


def clip_stem(input_path: str) -> str:
    path = Path(input_path)
    return path.name if path.is_dir() or not path.suffix else path.stem


def output_dir_for(input_path: str, output_root: str | None = None) -> str:
    path = Path(os.path.abspath(input_path))
    folder = f"{clip_stem(str(path))}_keyed"
    root = Path(os.path.abspath(output_root)) if output_root else path.parent
    return str(root / folder)


def preview_source(outputs: list[dict]) -> str | None:
    by_kind = {o.get("kind"): o for o in outputs if isinstance(o, dict)}
    for kind in PREVIEW_ORDER:
        item = by_kind.get(kind)
        if not item or item.get("type") != "image_sequence":
            continue
        pattern = item.get("pattern")
        if pattern:
            try:
                candidate = Path(pattern % int(item.get("first_frame", 0)))
            except (TypeError, ValueError):
                candidate = None
            if candidate and candidate.is_file():
                return str(candidate)
        folder = Path(item.get("path", ""))
        if folder.is_dir():
            frames = sorted(p for p in folder.iterdir() if is_image(p))
            if frames:
                return str(frames[0])
    return None


def output_folder(outputs: list[dict], fallback: str | None) -> str | None:
    for item in outputs:
        raw = item.get("path") if isinstance(item, dict) else None
        if raw and Path(raw).parent.is_dir():
            return str(Path(raw).parent)
    return fallback
