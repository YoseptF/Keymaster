from __future__ import annotations

import json
import os
import sys
from pathlib import Path

LANGUAGES = ("en", "es-419")
LANGUAGE_CHOICES = ("auto",) + LANGUAGES
DEFAULT_LANGUAGE = "en"
KEYS = ("language", "python", "core", "ffmpeg")
ENV_OVERRIDES = (("python", "KEYMASTER_PYTHON"), ("core", "KEYMASTER_CORE"))


def settings_path(env=None, platform: str | None = None) -> Path:
    env = os.environ if env is None else env
    platform = platform or sys.platform
    if env.get("KEYMASTER_SETTINGS"):
        return Path(env["KEYMASTER_SETTINGS"])
    if platform == "win32":
        base = env.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "Keymaster" / "settings.json"
    base = env.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "keymaster" / "settings.json"


def map_locale(value) -> str:
    return "es-419" if str(value or "").strip().lower().startswith("es") else DEFAULT_LANGUAGE


def normalize_language(value) -> str:
    return value if value in LANGUAGES else map_locale(value)


def windows_ui_locale() -> str:
    try:
        import ctypes
        import locale
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return locale.windows_locale.get(lang_id, "")
    except Exception:
        return ""


def os_ui_locale(env=None, platform: str | None = None) -> str:
    env = os.environ if env is None else env
    platform = platform or sys.platform
    if platform == "win32":
        return windows_ui_locale()
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = env.get(var, "")
        if value and value not in ("C", "POSIX") and not value.startswith("C."):
            return value
    return ""


def resolve_language(stored=None, env=None, platform: str | None = None) -> str:
    env = os.environ if env is None else env
    override = env.get("KEYMASTER_LANGUAGE", "")
    if override and override != "auto":
        return normalize_language(override)
    if stored in LANGUAGES:
        return stored
    return map_locale(os_ui_locale(env, platform))


def read_file(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def effective(env=None) -> dict:
    env = os.environ if env is None else env
    data = read_file(settings_path(env))
    for key, var in ENV_OVERRIDES:
        if env.get(var):
            data[key] = env[var]
    data["language"] = resolve_language(data.get("language"), env)
    return data


def write_file(path: Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def update(values: dict, env=None) -> dict:
    path = settings_path(env)
    data = read_file(path)
    data.update(values)
    write_file(path, data)
    return data


def add_ffmpeg_to_path(env=None) -> str | None:
    env = os.environ if env is None else env
    configured = read_file(settings_path(env)).get("ffmpeg")
    if not isinstance(configured, str) or not Path(configured).is_file():
        return None
    folder = str(Path(configured).resolve().parent)
    parts = env.get("PATH", "").split(os.pathsep)
    if folder not in parts:
        env["PATH"] = os.pathsep.join([folder] + [p for p in parts if p])
    return folder
