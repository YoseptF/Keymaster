from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import time
import zlib
from pathlib import Path


def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()
    time.sleep(float(os.environ.get("KEYMASTER_FAKE_DELAY", "0")))


def png(path: Path, width: int, height: int, channels: int, value: int) -> None:
    color_type = {1: 0, 3: 2, 4: 6}[channels]
    row = b"\x00" + bytes([value] * (width * channels))
    raw = row * height

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def settings_path() -> Path:
    if os.environ.get("KEYMASTER_SETTINGS"):
        return Path(os.environ["KEYMASTER_SETTINGS"])
    if sys.platform == "win32":
        return Path(os.environ["APPDATA"]) / "Keymaster" / "settings.json"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "keymaster" / "settings.json"


def read_settings() -> dict:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def os_ui_locale() -> str:
    if sys.platform == "win32":
        try:
            import ctypes
            import locale
            return locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), "")
        except Exception:
            return ""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if value and value not in ("C", "POSIX") and not value.startswith("C."):
            return value
    return ""


def resolve_language(stored) -> str:
    override = os.environ.get("KEYMASTER_LANGUAGE", "")
    if override and override != "auto":
        source = override
    elif stored in ("en", "es-419"):
        return stored
    else:
        source = os_ui_locale()
    return "es-419" if source.strip().lower().startswith("es") else "en"


def effective_settings() -> dict:
    data = read_settings()
    for key, var in (("python", "KEYMASTER_PYTHON"), ("core", "KEYMASTER_CORE")):
        if os.environ.get(var):
            data[key] = os.environ[var]
    data["language"] = resolve_language(data.get("language"))
    return data


def fail_if_asked() -> int:
    code = os.environ.get("KEYMASTER_FAKE_FAIL")
    if code:
        emit({"event": "error", "message_key": f"core.error.{code}", "params": {}, "detail": f"fake failure {code}"})
        return 130 if code == "cancelled" else 1
    return 0


def cmd_key(args) -> int:
    frames = args.frames if args.frames and args.frames > 0 else 4
    width, height = 16, 9
    start = max(0, args.start_frame)
    emit({"event": "start", "input": args.input, "first_frame": start, "frames": frames, "width": width, "height": height, "fps": 24.0})
    for i, phase in enumerate(("load", "prepass", "stage1", "stage2", "write")):
        emit({"event": "progress", "phase": phase, "fraction": round((i + 1) / 6, 4), "message_key": f"core.progress.{phase}"})
    failed = fail_if_asked()
    if failed:
        return failed
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.input).stem
    outputs = []
    for kind in args.outputs:
        channels = {"alpha": 1, "fg": 3, "cutout": 4, "checker": 3}[kind]
        if args.format == "video":
            path = out_dir / f"{stem}_{kind}.{'mov' if kind == 'cutout' else 'mp4'}"
            path.write_bytes(b"fake video")
            item = {"event": "output", "kind": kind, "type": "video", "path": str(path), "first_frame": start, "frames": frames}
        else:
            seq = out_dir / f"{stem}_{kind}"
            seq.mkdir(exist_ok=True)
            for f in range(start, start + frames):
                png(seq / f"{kind}_{f:06d}.png", width, height, channels, 200)
            item = {"event": "output", "kind": kind, "type": "image_sequence", "path": str(seq),
                    "pattern": str(seq / f"{kind}_%06d.png"), "first_frame": start, "frames": frames}
        emit(item)
        outputs.append(item)
    emit({"event": "progress", "phase": "write", "fraction": 1.0, "message_key": "core.progress.write"})
    emit({"event": "done", "outputs": outputs, "seconds": 0.1})
    return 0


def cmd_doctor(args) -> int:
    failing = {"no_gpu": "gpu", "ffmpeg_missing": "ffmpeg", "weights_missing": "weights",
               "dependency_missing": "torch"}.get(os.environ.get("KEYMASTER_FAKE_FAIL", ""), None)
    if os.environ.get("KEYMASTER_FAKE_FAIL") and failing is None:
        failing = "gpu"
    params = {"gpu": {"name": "Fake GPU", "memory": 24.0}, "ffmpeg": {"path": "/usr/bin/ffmpeg"},
              "weights": {"path": str(Path(__file__).resolve().parents[1] / "upstream")}, "torch": {"version": "2.9.1", "cuda": "12.8"}}
    checks = [{"id": i, "ok": i != failing, "message_key": f"core.doctor.{i}_{'missing' if i == failing else 'ok'}",
               "params": ({"missing": "corridorkey"} if i == "weights" else {}) if i == failing else params[i]}
              for i in ("gpu", "ffmpeg", "weights", "torch")]
    ok = failing is None
    emit({"event": "doctor", "ok": ok, "checks": checks})
    return 0 if ok else 1


def cmd_setup(args) -> int:
    emit({"event": "progress", "phase": "download", "fraction": 0.5, "message_key": "core.progress.download_corridorkey"})
    failed = fail_if_asked()
    if failed:
        return failed
    emit({"event": "progress", "phase": "download", "fraction": 1.0, "message_key": "core.progress.download_done"})
    emit({"event": "done", "outputs": [], "seconds": 0.0})
    return 0


def cmd_settings(args) -> int:
    if args.action == "get":
        data = effective_settings()
        print(json.dumps(data.get(args.key) if args.key else data))
        return 0
    if args.key not in ("language", "python", "core", "ffmpeg") or args.value is None or (
            args.key == "language" and args.value not in ("auto", "en", "es-419")):
        emit({"event": "error", "message_key": "core.error.invalid_setting",
              "params": {"key": args.key or "", "value": args.value or ""}, "detail": "fake invalid setting"})
        return 1
    data = read_settings()
    data[args.key] = args.value
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps(data))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="keymaster")
    sub = ap.add_subparsers(dest="command", required=True)
    key = sub.add_parser("key")
    key.add_argument("--input", required=True)
    key.add_argument("--output-dir", required=True)
    key.add_argument("--hint-first-frame")
    key.add_argument("--hint-video")
    key.add_argument("--hint-quality", type=float, default=0.95)
    key.add_argument("--despill", type=float, default=0.5)
    key.add_argument("--format", choices=("exr", "video"), default="exr")
    key.add_argument("--outputs", nargs="+", default=["alpha", "fg", "cutout"], choices=("alpha", "fg", "cutout", "checker"))
    key.add_argument("--start-frame", type=int, default=0)
    key.add_argument("--frames", type=int, default=0)
    key.add_argument("--low-vram", action="store_true")
    for name in ("doctor", "setup"):
        sub.add_parser(name)
    st = sub.add_parser("settings")
    st.add_argument("action", choices=("get", "set"))
    st.add_argument("key", nargs="?")
    st.add_argument("value", nargs="?")
    for p in sub.choices.values():
        p.add_argument("--json", action="store_true")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    return {"key": cmd_key, "doctor": cmd_doctor, "setup": cmd_setup, "settings": cmd_settings}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
