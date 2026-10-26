from __future__ import annotations

import argparse
import json
import signal
import sys
import traceback

from . import settings
from .errors import Cancelled, KeymasterError, classify
from .events import Emitter, claim_stdout

OUTPUT_KINDS = ("alpha", "fg", "cutout", "checker")
EXIT_CANCELLED = 130


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise KeymasterError(message_key="core.error.invalid_arguments", params={"problem": message}, detail=message)


def build_parser() -> argparse.ArgumentParser:
    ap = Parser(prog="keymaster")
    sub = ap.add_subparsers(dest="command", required=True, parser_class=Parser)
    key = sub.add_parser("key")
    key.add_argument("--input", required=True)
    key.add_argument("--output-dir", required=True)
    key.add_argument("--hint-first-frame")
    key.add_argument("--hint-video")
    key.add_argument("--hint-quality", type=float, default=0.95)
    key.add_argument("--despill", type=float, default=0.5)
    key.add_argument("--format", choices=("exr", "video"), default="exr")
    key.add_argument("--outputs", nargs="+", default=["alpha", "fg", "cutout"], choices=OUTPUT_KINDS)
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


def on_signal(signum, frame):
    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), signal.SIG_IGN)
    raise Cancelled()


def install_signal_handlers() -> None:
    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        if hasattr(signal, name):
            try:
                signal.signal(getattr(signal, name), on_signal)
            except ValueError:
                pass


def cmd_key(args, emitter: Emitter) -> int:
    from .keying import run_key
    run_key(args, emitter.emit)
    return 0


def cmd_doctor(args, emitter: Emitter) -> int:
    from .doctor import run_doctor
    report = run_doctor()
    emitter.emit(report)
    return 0 if report["ok"] else 1


def cmd_setup(args, emitter: Emitter) -> int:
    from .assets import run_setup
    run_setup(emitter.emit)
    return 0


def cmd_settings(args, emitter: Emitter, out) -> int:
    if args.action == "get":
        data = settings.effective()
        out.write(json.dumps(data.get(args.key) if args.key else data, ensure_ascii=False) + "\n")
        return 0
    if args.key not in settings.KEYS or args.value is None:
        raise KeymasterError(message_key="core.error.invalid_setting", params={"key": args.key or "", "value": args.value or ""},
                             detail=f"settings set needs one of {', '.join(settings.KEYS)} and a value")
    if args.key == "language" and args.value not in settings.LANGUAGE_CHOICES:
        raise KeymasterError(message_key="core.error.invalid_setting", params={"key": args.key, "value": args.value},
                             detail=f"language must be one of {', '.join(settings.LANGUAGE_CHOICES)}")
    data = settings.update({args.key: args.value})
    out.write(json.dumps(data, ensure_ascii=False) + "\n")
    return 0


def main(argv=None, out=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    json_mode = "--json" in argv
    real_process = out is None
    events = out if out is not None else sys.stdout
    if real_process and argv[:1] != ["settings"]:
        events = claim_stdout()
    emitter = Emitter(json_mode, stream=events)
    previous_stdout = sys.stdout
    if real_process:
        install_signal_handlers()
    else:
        sys.stdout = sys.stderr
    try:
        args = build_parser().parse_args(argv)
        if args.command == "settings":
            return cmd_settings(args, emitter, events)
        return {"key": cmd_key, "doctor": cmd_doctor, "setup": cmd_setup}[args.command](args, emitter)
    except BaseException as exc:
        if isinstance(exc, SystemExit):
            raise
        error = classify(exc)
        if error.message_key == "core.error.unknown":
            traceback.print_exception(exc, file=sys.stderr)
        emitter.emit(error.event())
        return EXIT_CANCELLED if error.message_key == "core.error.cancelled" else 1
    finally:
        if not real_process:
            sys.stdout = previous_stdout
        try:
            events.flush()
        except (OSError, ValueError):
            pass
