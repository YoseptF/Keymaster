from __future__ import annotations

from keymaster_app import clips
from keymaster_app.i18n import current, t


def core_text(message_key: str, params: dict | None = None) -> str | None:
    if message_key and current().has(message_key):
        return t(message_key, **(params or {}))
    return None


def phase_text(phase: str) -> str:
    names = {
        "load": t("app.phase.load"),
        "prepass": t("app.phase.prepass"),
        "stage1": t("app.phase.stage1"),
        "stage2": t("app.phase.stage2"),
        "write": t("app.phase.write"),
    }
    return names.get(phase, t("app.phase.working"))


def progress_text(clip: clips.Clip) -> str:
    return core_text(clip.message_key, clip.params) or phase_text(clip.phase)


def error_text(error: dict | None) -> str:
    if not error:
        return t("app.error.unknown")
    translated = core_text(error.get("message_key", ""), error.get("params"))
    if translated:
        return translated
    if error.get("launch"):
        return t("app.error.launch")
    if error.get("message_key"):
        return t("app.error.with_code", code=error["message_key"].rsplit(".", 1)[-1])
    if error.get("code") is not None:
        return t("app.error.exit_code", code=error["code"])
    return t("app.error.unknown")


def status_text(clip: clips.Clip) -> str:
    if clip.status == clips.RUNNING:
        return progress_text(clip) if clip.phase or clip.message_key else t("app.status.starting")
    if clip.status == clips.DONE:
        return t("app.status.done")
    if clip.status == clips.FAILED:
        return error_text(clip.error)
    if clip.status == clips.CANCELLED:
        return t("app.status.cancelled")
    return t("app.status.queued")


def check_name(check_id: str) -> str:
    names = {
        "gpu": t("app.doctor.name_gpu"),
        "ffmpeg": t("app.doctor.name_ffmpeg"),
        "weights": t("app.doctor.name_weights"),
        "torch": t("app.doctor.name_torch"),
    }
    return names.get(check_id, check_id)


def check_text(check: dict) -> str:
    translated = core_text(str(check.get("message_key", "")), check.get("params") if isinstance(check.get("params"), dict) else {})
    if translated:
        return translated
    name = check_name(str(check.get("id", "")))
    return t("app.doctor.check_ok", name=name) if check.get("ok") else t("app.doctor.check_missing", name=name)


def summary_text(queue: clips.ClipQueue) -> str:
    counts = queue.counts()
    return t("app.summary", done=counts[clips.DONE], total=len(queue),
             failed=counts[clips.FAILED] + counts[clips.CANCELLED])
