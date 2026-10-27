from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

MAX_CHANNEL = 128
EXTRA_ORDER = ("alpha", "fg", "checker")


@dataclass(frozen=True)
class SourceTiming:
    channel: int
    content_start: int
    content_end: int
    trim_start: int
    left: int
    right: int


@dataclass(frozen=True)
class Window:
    start: int
    left: int
    right: int


@dataclass
class PlannedStrip:
    kind: str
    type: str
    path: str
    channel: int
    window: Window
    files: list[str] = field(default_factory=list)
    blend: str = "REPLACE"
    mute: bool = False
    straight_alpha: bool = False


def output_window(src: SourceTiming, first_frame: int, frames: int) -> Optional[Window]:
    if frames <= 0:
        return None
    start = src.content_start - src.trim_start + first_frame
    end = start + frames
    left = src.left if start <= src.content_start else max(src.left, start)
    right = src.right if end >= src.content_end else min(src.right, end)
    if right <= left:
        return None
    return Window(start=start, left=left, right=right)


def frames_needed(src: SourceTiming, total: int) -> Optional[int]:
    if total <= 0:
        return None
    if src.right >= src.content_end:
        return total
    last = src.right - 1 - (src.content_start - src.trim_start)
    return min(total, max(1, last + 1))


def overlaps(a_left: int, a_right: int, b_left: int, b_right: int) -> bool:
    return a_left < b_right and b_left < a_right


def free_channel(occupied: Iterable[tuple[int, int, int]], above: int, left: int, right: int,
                 max_channel: int = MAX_CHANNEL) -> Optional[int]:
    taken = {channel for channel, o_left, o_right in occupied if overlaps(left, right, o_left, o_right)}
    for channel in range(above + 1, max_channel + 1):
        if channel not in taken:
            return channel
    return None


def sequence_files(output: dict) -> list[str]:
    pattern = output.get("pattern") or ""
    first = int(output.get("first_frame") or 0)
    frames = int(output.get("frames") or 0)
    if not pattern or frames <= 0:
        return []
    return [os.path.basename(pattern % number) for number in range(first, first + frames)]


def sequence_dir(output: dict) -> str:
    pattern = output.get("pattern") or ""
    return os.path.dirname(pattern) if pattern else output.get("path", "")


def plan(outputs: Sequence[dict], src: SourceTiming, occupied: Iterable[tuple[int, int, int]],
         add_extra: bool) -> tuple[list[PlannedStrip], list[dict]]:
    taken = list(occupied)
    by_kind = {o.get("kind"): o for o in outputs}
    order = ["cutout", *(EXTRA_ORDER if add_extra else ())]
    planned: list[PlannedStrip] = []
    skipped: list[dict] = []
    above = src.channel
    for kind in order:
        output = by_kind.get(kind)
        if not output:
            continue
        window = output_window(src, int(output.get("first_frame") or 0), int(output.get("frames") or 0))
        if window is None:
            skipped.append(output)
            continue
        channel = free_channel(taken, above, window.left, window.right)
        if channel is None:
            skipped.append(output)
            continue
        is_sequence = output.get("type") == "image_sequence"
        strip = PlannedStrip(
            kind=kind, type=output.get("type", ""),
            path=sequence_dir(output) if is_sequence else output.get("path", ""),
            files=sequence_files(output) if is_sequence else [],
            channel=channel, window=window,
            blend="ALPHA_OVER" if kind == "cutout" else "REPLACE",
            mute=kind != "cutout", straight_alpha=kind == "cutout")
        planned.append(strip)
        taken.append((channel, window.left, window.right))
        above = channel
    return planned, skipped
