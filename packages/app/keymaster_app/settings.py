from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

LANGUAGES = ("en", "es-419")
AUTO = "auto"
PREFERENCES = (AUTO, *LANGUAGES)
DEFAULT_LANGUAGE = "en"


def normalize_language(code: object) -> str:
    if isinstance(code, str) and code.strip().lower() == "es-419":
        return "es-419"
    return DEFAULT_LANGUAGE


def normalize_preference(code: object) -> str:
    if isinstance(code, str) and code.strip().lower() in LANGUAGES:
        return code.strip().lower()
    return AUTO


def language_from_locale(name: object) -> str:
    if isinstance(name, str) and name.strip().lower().startswith("es"):
        return "es-419"
    return DEFAULT_LANGUAGE


def _qt_ui_locale() -> str | None:
    try:
        from PySide6.QtCore import QLocale
    except ImportError:
        return None
    locale = QLocale.system()
    names = locale.uiLanguages()
    return names[0] if names else locale.name()


def _os_ui_locale() -> str | None:
    if sys.platform == "win32":
        try:
            import ctypes
            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        except (AttributeError, OSError):
            return None
        return "es" if langid & 0x3FF == 0x0A else "en"
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            return value
    return None


def system_language(use_qt: bool = True) -> str:
    name = (_qt_ui_locale() if use_qt else None) or _os_ui_locale()
    return language_from_locale(name)


def effective_language(preference: str, use_qt: bool = True) -> str:
    preference = normalize_preference(preference)
    return system_language(use_qt) if preference == AUTO else preference


def settings_path() -> Path:
    override = os.environ.get("KEYMASTER_SETTINGS")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "Keymaster" / "settings.json"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "keymaster" / "settings.json"


def load() -> dict:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(updates: dict) -> Path:
    path = settings_path()
    data = load()
    data.update(updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)
    return path


def save_language(preference: str) -> str:
    preference = normalize_preference(preference)
    save({"language": preference})
    return preference


@dataclass(frozen=True)
class Resolved:
    language: str
    python: str
    core: str | None
    preference: str = AUTO


def resolve(use_qt: bool = True) -> Resolved:
    data = load()
    preference = normalize_preference(data.get("language"))
    override = normalize_preference(os.environ.get("KEYMASTER_LANGUAGE"))
    language = override if override != AUTO else effective_language(preference, use_qt)
    python = os.environ.get("KEYMASTER_PYTHON") or data.get("python") or sys.executable
    core = os.environ.get("KEYMASTER_CORE") or data.get("core") or None
    return Resolved(language=language, python=str(python), core=str(core) if core else None, preference=preference)


def core_problem(resolved: Resolved) -> str | None:
    if not resolved.core or not (Path(resolved.core) / "keymaster").is_dir():
        return "core"
    if not Path(resolved.python).is_file():
        return "python"
    return None
