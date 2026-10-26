from __future__ import annotations

import json
import locale as pylocale
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

LANGUAGES = ("en", "es-419")
DEFAULT_LANGUAGE = "en"
AUTO = "auto"


@dataclass(frozen=True)
class Resolved:
    python: Optional[str]
    core: Optional[str]
    language: str
    path: Path


def settings_path(env: Optional[Mapping[str, str]] = None, platform: Optional[str] = None) -> Path:
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if env.get("KEYMASTER_SETTINGS"):
        return Path(env["KEYMASTER_SETTINGS"])
    if platform == "win32":
        base = env.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "Keymaster" / "settings.json"
    base = env.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "keymaster" / "settings.json"


def read(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def configured_language(env: Optional[Mapping[str, str]] = None, platform: Optional[str] = None) -> Optional[str]:
    env = os.environ if env is None else env
    if env.get("KEYMASTER_LANGUAGE") in LANGUAGES:
        return env["KEYMASTER_LANGUAGE"]
    value = read(settings_path(env, platform)).get("language", AUTO)
    return value if value in LANGUAGES else None


def language_from_locale(name: Optional[str]) -> str:
    name = (name or "").strip().lower()
    return "es-419" if name.startswith(("es", "spanish")) else DEFAULT_LANGUAGE


def windows_locale() -> Optional[str]:
    try:
        import ctypes
        buffer = ctypes.create_unicode_buffer(85)
        if ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, len(buffer)):
            return buffer.value
    except (AttributeError, OSError, ImportError):
        pass
    return None


def os_locale(env: Optional[Mapping[str, str]] = None, platform: Optional[str] = None) -> Optional[str]:
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if platform == "win32":
        found = windows_locale()
        if found:
            return found
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        value = (env.get(var) or "").split(":")[0]
        if value and value not in ("C", "POSIX") and not value.startswith(("C.", "POSIX.")):
            return value
    try:
        return pylocale.getlocale()[0]
    except (ValueError, TypeError):
        return None


def resolve(env: Optional[Mapping[str, str]] = None, platform: Optional[str] = None,
            locale: Optional[str] = None) -> Resolved:
    env = os.environ if env is None else env
    path = settings_path(env, platform)
    data = read(path)
    python = env.get("KEYMASTER_PYTHON") or data.get("python") or None
    core = env.get("KEYMASTER_CORE") or data.get("core") or None
    language = configured_language(env, platform) or language_from_locale(locale or os_locale(env, platform))
    return Resolved(python=python, core=core, language=language, path=path)
