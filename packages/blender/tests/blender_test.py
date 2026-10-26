import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

import addon_utils
import bpy

REPO = "user_default"
MODULE = f"bl_ext.{REPO}.keymaster"


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("source", "zip"), required=True)
    ap.add_argument("--source")
    ap.add_argument("--zip")
    ap.add_argument("--tmp", required=True)
    return ap.parse_args(argv)


class Recorder:
    def __init__(self, texts):
        self.texts = texts

    def _record(self, *args, **kwargs):
        if kwargs.get("text"):
            self.texts.append(kwargs["text"])
        return Recorder(self.texts)

    label = prop = operator = progress = _record

    def column(self, *args, **kwargs):
        return Recorder(self.texts)

    row = box = grid_flow = column

    def separator(self, *args, **kwargs):
        pass


class Host:
    def __init__(self):
        self.layout = Recorder([])


def draw(cls, context=None, host=None):
    host = host or Host()
    cls.draw(host, context or bpy.context)
    return host.layout.texts


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def install(args):
    repo_dir = Path(bpy.utils.user_resource("EXTENSIONS", path=REPO, create=True))
    check(str(repo_dir).startswith(args.tmp), f"extensions dir {repo_dir} is not isolated under {args.tmp}")
    if args.mode == "source":
        target = repo_dir / "keymaster"
        if target.is_symlink() or target.exists():
            target.unlink() if target.is_symlink() else shutil.rmtree(target)
        target.symlink_to(Path(args.source).resolve(), target_is_directory=True)
        bpy.ops.extensions.repo_refresh_all()
        addon_utils.enable(MODULE, default_set=True, handle_error=None)
    else:
        result = bpy.ops.extensions.package_install_files(filepath=args.zip, repo=REPO, enable_on_install=True)
        check(result == {"FINISHED"}, f"install from disk returned {result}")
    check(MODULE in bpy.context.preferences.addons, "extension is not enabled")
    check(hasattr(bpy.types.Scene, "keymaster"), "scene settings are not registered")
    return importlib.import_module(f"{MODULE}.ui"), importlib.import_module(f"{MODULE}.i18n")


def settings_file():
    return Path(os.environ["KEYMASTER_SETTINGS"])


def test_language(ui, i18n):
    en = json.loads((Path(i18n.table_dirs()[0]) / "en.json").read_text(encoding="utf-8"))
    es = json.loads((Path(i18n.table_dirs()[0]) / "es-419.json").read_text(encoding="utf-8"))
    prefs = bpy.context.preferences.addons[MODULE].preferences
    prefs.language = "en"
    check(json.loads(settings_file().read_text())["language"] == "en", "language en not written")
    texts = draw(ui.KEYMASTER_PT_panel)
    check(en["blender.key.label"] in texts, f"English panel missing Key button: {texts}")
    prefs.language = "es-419"
    data = json.loads(settings_file().read_text())
    check(data["language"] == "es-419", f"settings not updated: {data}")
    check(prefs.language == "es-419", "preference does not read back es-419")
    texts = draw(ui.KEYMASTER_PT_panel)
    check(es["blender.key.label"] in texts, f"Spanish panel missing Key button after switch: {texts}")
    check(es["blender.prefs.language"] in draw(ui.KEYMASTER_preferences),
          "Spanish preferences missing language label")
    settings_file().write_text(json.dumps({**data, "language": "en"}))
    time.sleep(i18n.REFRESH_SECONDS + 0.1)
    texts = draw(ui.KEYMASTER_PT_panel)
    check(en["blender.key.label"] in texts, f"external language change not picked up on redraw: {texts}")
    check(prefs.language == "en", "preference does not follow the shared file")
    print("ok language switch")


def wait(ui, attr, timeout=30.0):
    deadline = time.monotonic() + timeout
    while getattr(ui.session, attr) is not None:
        check(time.monotonic() < deadline, f"{attr} run did not finish")
        ui.tick()
        time.sleep(0.02)


def editor():
    return bpy.context.scene.sequence_editor_create()


def reset_scene():
    ed = editor()
    for strip in list(ed.strips):
        ed.strips.remove(strip)
    scene = bpy.context.scene
    scene.render.fps = 24
    scene.render.fps_base = 1.0
    props = scene.keymaster
    props.out_alpha = props.out_fg = props.out_cutout = True
    props.out_checker = False
    props.add_extra = True
    return ed


def frame_number(strip, frame):
    elem = strip.strip_elem_from_frame(frame)
    check(elem is not None, f"{strip.name} has no element at {frame}")
    return int(re.findall(r"(\d+)", elem.filename)[-1])


def run_key(ui):
    result = bpy.ops.keymaster.key()
    check(result == {"FINISHED"}, f"key operator returned {result}: {[l.text() for l in ui.session.key_lines]}")
    check(ui.session.key is not None, "no key run started")
    wait(ui, "key")


def check_outputs(ui, src, expected_source_frame):
    ed = editor()
    lines = [line.message_key for line in ui.session.key_lines]
    check(lines and lines[0] == "blender.status.done", f"key did not finish cleanly: {lines}")
    by_kind = {s.name.rsplit(".", 1)[-1]: s for s in ed.strips if s != src}
    check(set(by_kind) == {"cutout", "alpha", "fg"}, f"unexpected strips {sorted(by_kind)}")
    cutout = by_kind["cutout"]
    check(cutout.channel == src.channel + 1, f"cutout on channel {cutout.channel}, source on {src.channel}")
    check(cutout.blend_type == "ALPHA_OVER", f"cutout blend is {cutout.blend_type}")
    check(cutout.alpha_mode == "STRAIGHT", "cutout alpha is not straight")
    check(not cutout.mute, "cutout is muted")
    check(by_kind["alpha"].mute and by_kind["fg"].mute, "extra strips are not muted")
    check(sorted(s.channel for s in by_kind.values()) == [src.channel + 1, src.channel + 2, src.channel + 3],
          "extra strips are not stacked above the cutout")
    for strip in by_kind.values():
        check((strip.left_handle, strip.right_handle) == (src.left_handle, src.right_handle),
              f"{strip.name} spans {strip.left_handle}-{strip.right_handle}, source {src.left_handle}-{src.right_handle}")
        for frame in range(src.left_handle, src.right_handle):
            got = frame_number(strip, frame)
            want = expected_source_frame(frame)
            check(got == want, f"{strip.name} shows frame {got} at {frame}, source shows {want}")


def make_frames(directory, count):
    directory.mkdir(parents=True, exist_ok=True)
    import struct
    import zlib

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    for i in range(count):
        raw = (b"\x00" + bytes([i * 10 % 256, 200, 0] * 16)) * 9
        header = struct.pack(">IIBBBBB", 16, 9, 8, 2, 0, 0, 0)
        (directory / f"plate_{i:04d}.png").write_bytes(
            b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def test_image_sequence(ui, tmp):
    ed = reset_scene()
    plate = tmp / "plate"
    make_frames(plate, 20)
    src = ed.strips.new_image(name="plate", filepath=str(plate / "plate_0000.png"), channel=1, frame_start=50)
    for i in range(1, 20):
        src.elements.append(f"plate_{i:04d}.png")
    src.left_handle = 53
    src.right_handle = 66
    ed.active_strip = src
    bpy.context.scene.keymaster.output_dir = str(tmp / "out-seq")
    run_key(ui)
    check_outputs(ui, src, lambda frame: frame_number(src, frame))
    print("ok image sequence strip")


def test_movie(ui, tmp):
    if not shutil.which("ffmpeg"):
        print("skip movie strip: ffmpeg not found")
        return
    clip = tmp / "clip.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=64x36:rate=24",
                    "-frames:v", "30", "-pix_fmt", "yuv420p", str(clip)], check=True)
    ed = reset_scene()
    src = ed.strips.new_movie(name="clip", filepath=str(clip), channel=2, frame_start=10)
    src.content_trim_start = 3
    src.left_handle = 16
    src.right_handle = 35
    origin = src.content_start - src.content_trim_start
    check(origin == 10, f"unexpected source origin {origin}")
    ed.active_strip = src
    bpy.context.scene.keymaster.output_dir = str(tmp / "out-movie")
    run_key(ui)
    check_outputs(ui, src, lambda frame: frame - origin)
    print("ok movie strip")


def test_cancel_and_errors(ui, tmp):
    ed = reset_scene()
    plate = tmp / "plate"
    src = ed.strips.new_image(name="plate", filepath=str(plate / "plate_0000.png"), channel=1, frame_start=1)
    for i in range(1, 20):
        src.elements.append(f"plate_{i:04d}.png")
    ed.active_strip = src
    bpy.context.scene.keymaster.output_dir = str(tmp / "out-cancel")
    os.environ["KEYMASTER_FAKE_DELAY"] = "0.5"
    try:
        check(bpy.ops.keymaster.key() == {"FINISHED"}, "key did not start")
        deadline = time.monotonic() + 5
        while ui.session.key.state.fraction <= 0 and time.monotonic() < deadline:
            ui.tick()
            time.sleep(0.02)
        check(ui.session.key.state.fraction > 0, "no progress before cancel")
        texts = draw(ui.KEYMASTER_PT_panel)
        cancel = ui.t("blender.cancel.label")
        check(cancel in texts, f"no cancel button while running: {texts}")
        check(bpy.ops.keymaster.key.poll() is False, "key can start twice")
        check(bpy.ops.keymaster.cancel() == {"FINISHED"}, "cancel failed")
        wait(ui, "key", timeout=15)
    finally:
        del os.environ["KEYMASTER_FAKE_DELAY"]
    check([l.message_key for l in ui.session.key_lines] == ["blender.status.cancelled"], "cancel not reported")
    check(len(ed.strips) == 1, "strips were added after cancel")
    os.environ["KEYMASTER_FAKE_FAIL"] = "no_gpu"
    try:
        run_key(ui)
    finally:
        del os.environ["KEYMASTER_FAKE_FAIL"]
    line = ui.session.key_lines[0]
    check(line.message_key == "core.error.no_gpu" and line.icon == "ERROR", f"core error not surfaced: {line}")
    check(line.text() and line.text() != "core.error.no_gpu", f"core error has no readable text: {line.text()}")
    check(len(ed.strips) == 1, "strips were added after a failure")
    print("ok cancel and errors")


def test_doctor(ui):
    check(bpy.ops.keymaster.doctor() == {"FINISHED"}, "doctor did not start")
    wait(ui, "doctor")
    keys = [l.message_key for l in ui.session.doctor_lines]
    check(keys and keys[0] == "blender.doctor.ok" and len(keys) == 5, f"doctor results: {keys}")
    print("ok doctor")


def test_installed(ui, i18n):
    dirs = [Path(d) for d in i18n.table_dirs()]
    installed = Path(bpy.utils.user_resource("EXTENSIONS", path=REPO)) / "keymaster"
    check(all(installed.resolve() in d.resolve().parents for d in dirs), f"tables not bundled: {dirs}")
    check(all((d / "en.json").is_file() and (d / "es-419.json").is_file() for d in dirs), "bundled tables missing")
    check(i18n.translator.tables["es-419"].get("blender.key.label"), "Spanish table not loaded")
    print("ok installed zip")


def main():
    args = parse_args()
    tmp = Path(args.tmp)
    ui, i18n = install(args)
    if args.mode == "zip":
        test_installed(ui, i18n)
        test_language(ui, i18n)
        test_image_sequence(ui, tmp)
        return
    test_language(ui, i18n)
    test_image_sequence(ui, tmp)
    test_movie(ui, tmp)
    test_cancel_and_errors(ui, tmp)
    test_doctor(ui)
    addon_utils.disable(MODULE, default_set=True)
    check(not hasattr(bpy.types.Scene, "keymaster"), "disable left scene settings registered")
    print("ok disable")


try:
    main()
except Exception:
    traceback.print_exc()
    sys.stdout.flush()
    sys.exit(1)
