from __future__ import annotations

import os
from dataclasses import dataclass, field

OUTPUT_KINDS = ("alpha", "fg", "cutout", "checker")
DEFAULT_OUTPUTS = ("alpha", "fg", "cutout")
FORMATS = ("exr", "video")


@dataclass
class KeyOptions:
    hint_quality: float = 0.95
    despill: float = 0.5
    outputs: tuple[str, ...] = field(default_factory=lambda: DEFAULT_OUTPUTS)
    format: str = "exr"
    output_root: str | None = None
    low_vram: bool = False

    def validate(self) -> str | None:
        if not self.outputs:
            return "no_outputs"
        if self.format not in FORMATS:
            return "format"
        return None


def _number(value: float) -> str:
    return f"{max(0.0, min(1.0, float(value))):g}"


def key_command(python: str, input_path: str, output_dir: str, options: KeyOptions, hint: str | None = None) -> list[str]:
    cmd = [python, "-m", "keymaster", "key",
           "--input", os.path.abspath(input_path),
           "--output-dir", os.path.abspath(output_dir)]
    if hint:
        cmd += ["--hint-first-frame", os.path.abspath(hint)]
    cmd += ["--hint-quality", _number(options.hint_quality),
            "--despill", _number(options.despill),
            "--format", options.format,
            "--outputs", *[k for k in OUTPUT_KINDS if k in options.outputs]]
    if options.low_vram:
        cmd.append("--low-vram")
    cmd.append("--json")
    return cmd


def doctor_command(python: str) -> list[str]:
    return [python, "-m", "keymaster", "doctor", "--json"]
