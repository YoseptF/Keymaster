import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty, StringProperty
from bpy.types import AddonPreferences, Operator, Panel, PropertyGroup

from . import events, placement, runner, settings
from .i18n import t, translator

ADDON = __package__
SUPPORTED_TYPES = {"MOVIE", "IMAGE"}
TICK_SECONDS = 0.1
REDRAW_AREAS = {"SEQUENCE_EDITOR", "PREFERENCES"}


@dataclass
class Line:
    message_key: Optional[str]
    params: dict = field(default_factory=dict)
    icon: str = "INFO"
    fallback: Optional["Line"] = None

    def text(self) -> str:
        if self.fallback is not None and not translator.has(self.message_key):
            return self.fallback.text()
        return translator.translate(self.message_key, self.params)


class Session:
    def __init__(self) -> None:
        self.key: Optional[runner.CoreRun] = None
        self.key_meta: dict = {}
        self.key_lines: list[Line] = []
        self.doctor: Optional[runner.CoreRun] = None
        self.doctor_lines: list[Line] = []

    def key_running(self) -> bool:
        return self.key is not None and not self.key.state.finished

    def doctor_running(self) -> bool:
        return self.doctor is not None and not self.doctor.state.finished


session = Session()
_enum_items: dict = {}


def cached_items(name: str, entries: list) -> list:
    _enum_items[name] = entries
    return entries


def format_items(self, context):
    return cached_items("format", [
        ("exr", t("blender.format.exr"), t("blender.format.exr_tip"), 0),
        ("video", t("blender.format.video"), t("blender.format.video_tip"), 1),
    ])


def language_items(self, context):
    return cached_items("language", [
        ("en", t("blender.language.en"), "", 0),
        ("es-419", t("blender.language.es_419"), "", 1),
    ])


def get_language(self) -> int:
    return settings.LANGUAGES.index(settings.file_language())


def set_language(self, value: int) -> None:
    settings.set_language(settings.LANGUAGES[value])
    translator.invalidate()
    redraw(everything=True)


def redraw(everything: bool = False) -> None:
    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return
    for window in wm.windows:
        for area in window.screen.areas:
            if everything or area.type in REDRAW_AREAS:
                area.tag_redraw()


def active_source(context):
    scene = getattr(context, "scene", None)
    editor = scene.sequence_editor if scene else None
    strip = editor.active_strip if editor else None
    return strip if strip is not None and strip.type in SUPPORTED_TYPES else None


def abspath(path: str) -> str:
    return os.path.normpath(bpy.path.abspath(path)) if path else ""


def source_input(strip) -> str:
    if strip.type == "MOVIE":
        return abspath(strip.filepath)
    return abspath(strip.directory).rstrip("\\/") or abspath(strip.directory)


def output_base(props) -> str:
    if props.output_dir:
        return abspath(props.output_dir)
    if bpy.data.filepath:
        return abspath("//keymaster")
    return os.path.join(tempfile.gettempdir(), "keymaster")


def selected_outputs(props) -> list:
    return [kind for kind in runner.OUTPUT_KINDS if getattr(props, f"out_{kind}")]


def ensure_timer() -> None:
    if not bpy.app.timers.is_registered(tick):
        bpy.app.timers.register(tick, first_interval=TICK_SECONDS)


def tick():
    busy = False
    if session.key is not None:
        state = session.key.step()
        if state.finished:
            finish_key()
        else:
            busy = True
    if session.doctor is not None:
        state = session.doctor.step()
        if state.finished:
            finish_doctor()
        else:
            busy = True
    redraw()
    return TICK_SECONDS if busy else None


def core_error_line(error: Optional[dict]) -> Line:
    error = error or {}
    key = error.get("message_key")
    if not key:
        return Line(message_key="blender.error.core_crashed", icon="ERROR")
    return Line(message_key=key, params=error.get("params") or {}, icon="ERROR",
                fallback=Line(message_key="blender.error.core_failed", params={"code": key}))


def finish_key() -> None:
    run, meta = session.key, session.key_meta
    session.key = None
    state = run.state
    if state.status == events.CANCELLED:
        session.key_lines = [Line(message_key="blender.status.cancelled", icon="CANCEL")]
        return
    if state.status == events.FAILED:
        detail = (state.error or {}).get("detail") or run.stderr_tail()
        if detail:
            print(f"Keymaster: {detail}")
        session.key_lines = [core_error_line(state.error)]
        return
    session.key_lines = place_outputs(meta, state.final_outputs())


def source_timing(strip) -> placement.SourceTiming:
    return placement.SourceTiming(
        channel=strip.channel, content_start=int(strip.content_start), content_end=int(strip.content_end),
        trim_start=int(strip.content_trim_start), left=int(strip.left_handle), right=int(strip.right_handle))


def source_frames(strip) -> int:
    if strip.type == "IMAGE":
        return len(strip.elements)
    return int(strip.content_trim_start) + int(strip.content_duration) + int(strip.content_trim_end)


def strip_container(scene, strip):
    parent = strip.parent_meta()
    return parent.strips if parent is not None else scene.sequence_editor.strips


def copy_look(src, dst) -> None:
    for attr in ("offset_x", "offset_y", "scale_x", "scale_y", "rotation"):
        setattr(dst.transform, attr, getattr(src.transform, attr))
    dst.transform.origin = tuple(src.transform.origin)
    for attr in ("min_x", "max_x", "min_y", "max_y"):
        setattr(dst.crop, attr, getattr(src.crop, attr))
    dst.use_flip_x = src.use_flip_x
    dst.use_flip_y = src.use_flip_y


def create_strip(container, src, planned: placement.PlannedStrip):
    name = f"{src.name}.{planned.kind}"
    window = planned.window
    if planned.type == "image_sequence":
        if not planned.files:
            raise RuntimeError(planned.path)
        first = os.path.join(planned.path, planned.files[0])
        strip = container.new_image(name=name, filepath=first, channel=planned.channel, frame_start=window.start)
        for filename in planned.files[1:]:
            strip.elements.append(filename)
    else:
        strip = container.new_movie(name=name, filepath=planned.path, channel=planned.channel,
                                    frame_start=window.start)
    if window.left >= strip.right_handle:
        strip.right_handle = window.right
        strip.left_handle = window.left
    else:
        strip.left_handle = window.left
        strip.right_handle = window.right
    strip.blend_type = planned.blend
    strip.mute = planned.mute
    if planned.straight_alpha:
        strip.alpha_mode = "STRAIGHT"
    strip.select = False
    copy_look(src, strip)
    return strip


def place_outputs(meta: dict, outputs: list) -> list:
    scene = bpy.data.scenes.get(meta.get("scene", ""))
    editor = scene.sequence_editor if scene else None
    src = editor.strips_all.get(meta.get("strip", "")) if editor else None
    if src is None:
        return [Line(message_key="blender.error.source_gone", icon="ERROR")]
    container = strip_container(scene, src)
    timing = source_timing(src)
    occupied = [(s.channel, int(s.left_handle), int(s.right_handle)) for s in container]
    planned, skipped = placement.plan(outputs, timing, occupied, meta.get("add_extra", False))
    lines: list = []
    created = 0
    for item in planned:
        try:
            create_strip(container, src, item)
            created += 1
        except (RuntimeError, OSError, TypeError) as exc:
            print(f"Keymaster: {exc}")
            lines.append(Line(message_key="blender.error.load_output", params={"path": item.path}, icon="ERROR"))
    if skipped:
        lines.append(Line(message_key="blender.status.skipped", params={"count": len(skipped)}, icon="ERROR"))
    if created:
        lines.insert(0, Line(message_key="blender.status.done", params={"count": created}, icon="CHECKMARK"))
    lines.append(Line(message_key="blender.status.written", params={"path": meta.get("output_dir", "")},
                      icon="FILE_FOLDER"))
    return lines


def finish_doctor() -> None:
    run = session.doctor
    session.doctor = None
    state = run.state
    report = state.doctor
    if report is None:
        session.doctor_lines = [core_error_line(state.error)]
        return
    lines = []
    for check in report.get("checks") or []:
        lines.append(Line(message_key=check.get("message_key"), params=check.get("params") or {},
                          icon="CHECKMARK" if check.get("ok") else "ERROR",
                          fallback=Line(message_key="blender.doctor.fallback", params={"id": check.get("id", "")})))
    if report.get("ok"):
        lines.insert(0, Line(message_key="blender.doctor.ok", icon="CHECKMARK"))
    else:
        lines.insert(0, Line(message_key="blender.doctor.failed", icon="ERROR"))
    session.doctor_lines = lines


def setup_problem(resolved: settings.Resolved) -> Optional[Line]:
    if not resolved.core or not os.path.isdir(resolved.core):
        return Line(message_key="blender.error.no_core", icon="ERROR")
    if not resolved.python:
        return Line(message_key="blender.error.no_python", icon="ERROR")
    return None


def draw_lines(layout, lines: list) -> None:
    for line in lines:
        layout.label(text=line.text(), icon=line.icon, translate=False)


class KEYMASTER_OT_key(Operator):
    bl_idname = "keymaster.key"
    bl_options = {"REGISTER"}

    @classmethod
    def description(cls, context, properties):
        return t("blender.key.tooltip")

    @classmethod
    def poll(cls, context):
        if session.key_running():
            cls.poll_message_set(t("blender.key.busy"))
            return False
        if active_source(context) is None:
            cls.poll_message_set(t("blender.panel.no_strip"))
            return False
        return True

    def fail(self, line: Line):
        session.key_lines = [line]
        self.report({"ERROR"}, line.text())
        return {"CANCELLED"}

    def execute(self, context):
        strip = active_source(context)
        props = context.scene.keymaster
        resolved = settings.resolve()
        problem = setup_problem(resolved)
        if problem is not None:
            return self.fail(problem)
        outputs = selected_outputs(props)
        if not outputs:
            return self.fail(Line(message_key="blender.error.no_outputs", icon="ERROR"))
        source = source_input(strip)
        if not source or not os.path.exists(source):
            return self.fail(Line(message_key="blender.error.input_missing", params={"path": source}, icon="ERROR"))
        hint = abspath(props.hint_image) if props.hint_image else None
        if hint and not os.path.isfile(hint):
            return self.fail(Line(message_key="blender.error.hint_missing", params={"path": hint}, icon="ERROR"))
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = runner.unique_dir(output_base(props), runner.run_dir_name(strip.name, stamp))
        options = runner.KeyOptions(
            input=source, output_dir=output_dir, hint_first_frame=hint, hint_quality=props.hint_quality,
            despill=props.despill, format=props.format, outputs=outputs, low_vram=props.low_vram,
            frames=placement.frames_needed(source_timing(strip), source_frames(strip)))
        argv = runner.key_command(resolved.python, options)
        print(f"Keymaster: {runner.describe(argv)}")
        session.key_lines = []
        session.key_meta = {"scene": context.scene.name, "strip": strip.name, "add_extra": props.add_extra,
                            "output_dir": output_dir}
        session.key = runner.CoreRun(argv, cwd=resolved.core).start()
        ensure_timer()
        return {"FINISHED"}


class KEYMASTER_OT_cancel(Operator):
    bl_idname = "keymaster.cancel"
    bl_options = {"REGISTER"}

    @classmethod
    def description(cls, context, properties):
        return t("blender.cancel.tooltip")

    @classmethod
    def poll(cls, context):
        return session.key_running()

    def execute(self, context):
        session.key.cancel()
        ensure_timer()
        return {"FINISHED"}


class KEYMASTER_OT_doctor(Operator):
    bl_idname = "keymaster.doctor"
    bl_options = {"REGISTER"}

    @classmethod
    def description(cls, context, properties):
        return t("blender.doctor.tooltip")

    @classmethod
    def poll(cls, context):
        return not session.doctor_running()

    def execute(self, context):
        resolved = settings.resolve()
        problem = setup_problem(resolved)
        if problem is not None:
            session.doctor_lines = [problem]
            return {"CANCELLED"}
        session.doctor_lines = []
        session.doctor = runner.CoreRun(runner.doctor_command(resolved.python), cwd=resolved.core).start()
        ensure_timer()
        return {"FINISHED"}


class KEYMASTER_PT_panel(Panel):
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"

    def draw(self, context):
        layout = self.layout
        if session.key_running():
            state = session.key.state
            layout.label(text=t("blender.panel.strip", name=session.key_meta.get("strip", "")), icon="SEQUENCE",
                         translate=False)
            if not state.message_key:
                text = t("blender.progress.starting")
            elif translator.has(state.message_key):
                text = translator.translate(state.message_key)
            else:
                text = t("blender.progress.fallback")
            layout.progress(factor=state.fraction, type="BAR", text=text, translate=False)
            layout.operator("keymaster.cancel", text=t("blender.cancel.label"), icon="CANCEL", translate=False)
            return
        strip = active_source(context)
        if strip is None:
            layout.label(text=t("blender.panel.no_strip"), icon="INFO", translate=False)
        else:
            layout.label(text=t("blender.panel.strip", name=strip.name), icon="SEQUENCE", translate=False)
        props = context.scene.keymaster
        col = layout.column()
        col.label(text=t("blender.panel.hint"), translate=False)
        col.prop(props, "hint_image", text="", translate=False)
        col.prop(props, "hint_quality", text=t("blender.option.hint_quality"), slider=True, translate=False)
        col.prop(props, "despill", text=t("blender.option.despill"), slider=True, translate=False)
        col.separator()
        col.label(text=t("blender.panel.outputs"), translate=False)
        grid = col.grid_flow(columns=2, even_columns=True)
        for kind in runner.OUTPUT_KINDS:
            grid.prop(props, f"out_{kind}", text=t(f"blender.output.{kind}"), translate=False)
        col.prop(props, "format", text=t("blender.option.format"), translate=False)
        col.prop(props, "add_extra", text=t("blender.option.add_extra"), translate=False)
        col.prop(props, "low_vram", text=t("blender.option.low_vram"), translate=False)
        col.label(text=t("blender.option.output_dir"), translate=False)
        col.prop(props, "output_dir", text="", translate=False)
        layout.separator()
        row = layout.row()
        row.scale_y = 1.4
        row.operator("keymaster.key", text=t("blender.key.label"), icon="IMAGE_RGB_ALPHA", translate=False)
        draw_lines(layout.column(), session.key_lines)


class KEYMASTER_preferences(AddonPreferences):
    bl_idname = ADDON

    language: EnumProperty(items=language_items, get=get_language, set=set_language)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "language", text=t("blender.prefs.language"), translate=False)
        resolved = settings.resolve()
        box = layout.box()
        missing = t("blender.prefs.not_set")
        box.label(text=t("blender.prefs.core", path=resolved.core or missing), icon="FILE_FOLDER", translate=False)
        box.label(text=t("blender.prefs.python", path=resolved.python or missing), icon="SCRIPT", translate=False)
        box.label(text=t("blender.prefs.settings_file", path=str(resolved.path)), icon="PREFERENCES",
                  translate=False)
        row = layout.row()
        row.operator("keymaster.doctor", text=t("blender.doctor.label"), icon="CHECKMARK", translate=False)
        if session.doctor_running():
            row.label(text=t("blender.doctor.running"), translate=False)
        draw_lines(layout.column(), session.doctor_lines)


def scene_properties() -> dict:
    return {
        "hint_image": StringProperty(name=t("blender.option.hint_image"),
                                     description=t("blender.option.hint_image_tip"), subtype="FILE_PATH"),
        "hint_quality": FloatProperty(name=t("blender.option.hint_quality"),
                                      description=t("blender.option.hint_quality_tip"), default=0.95, min=0.0,
                                      max=1.0),
        "despill": FloatProperty(name=t("blender.option.despill"), description=t("blender.option.despill_tip"),
                                 default=0.5, min=0.0, max=1.0),
        "out_alpha": BoolProperty(name=t("blender.output.alpha"), description=t("blender.output.alpha_tip"),
                                  default=True),
        "out_fg": BoolProperty(name=t("blender.output.fg"), description=t("blender.output.fg_tip"), default=True),
        "out_cutout": BoolProperty(name=t("blender.output.cutout"), description=t("blender.output.cutout_tip"),
                                   default=True),
        "out_checker": BoolProperty(name=t("blender.output.checker"), description=t("blender.output.checker_tip"),
                                    default=False),
        "format": EnumProperty(name=t("blender.option.format"), description=t("blender.option.format_tip"),
                               items=format_items, default=0),
        "add_extra": BoolProperty(name=t("blender.option.add_extra"), description=t("blender.option.add_extra_tip"),
                                  default=False),
        "low_vram": BoolProperty(name=t("blender.option.low_vram"), description=t("blender.option.low_vram_tip"),
                                 default=False),
        "output_dir": StringProperty(name=t("blender.option.output_dir"),
                                     description=t("blender.option.output_dir_tip"), subtype="DIR_PATH"),
    }


KeymasterSceneSettings = None
CLASSES = (KEYMASTER_OT_key, KEYMASTER_OT_cancel, KEYMASTER_OT_doctor, KEYMASTER_PT_panel, KEYMASTER_preferences)


def register():
    global KeymasterSceneSettings
    KEYMASTER_OT_key.bl_label = t("blender.key.label")
    KEYMASTER_OT_cancel.bl_label = t("blender.cancel.label")
    KEYMASTER_OT_doctor.bl_label = t("blender.doctor.label")
    KEYMASTER_PT_panel.bl_label = t("blender.panel.title")
    KEYMASTER_PT_panel.bl_category = t("blender.panel.tab")
    KeymasterSceneSettings = type("KEYMASTER_PG_settings", (PropertyGroup,), {"__annotations__": scene_properties()})
    bpy.utils.register_class(KeymasterSceneSettings)
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.keymaster = PointerProperty(type=KeymasterSceneSettings)


def unregister():
    global KeymasterSceneSettings
    for run in (session.key, session.doctor):
        if run is not None:
            run.cancel()
    session.key = None
    session.doctor = None
    if bpy.app.timers.is_registered(tick):
        bpy.app.timers.unregister(tick)
    del bpy.types.Scene.keymaster
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    if KeymasterSceneSettings is not None:
        bpy.utils.unregister_class(KeymasterSceneSettings)
        KeymasterSceneSettings = None
