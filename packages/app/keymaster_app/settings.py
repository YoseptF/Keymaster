from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

LANGUAGES = ("en", "es-419")
DEFAULT_LANGUAGE = "en"


def normalize_language(code: object) -> str:
    if isinstance(code, str) and code.strip().lower() == "es-419":
        return "es-419"
    return DEFAULT_LANGUAGE


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


def save_language(code: str) -> str:
    language = normalize_language(code)
    save({"language": language})
    return language


@dataclass(frozen=True)
class Resolved:
    language: str
    python: str
    core: str | None


def resolve() -> Resolved:
    data = load()
    language = normalize_language(os.environ.get("KEYMASTER_LANGUAGE") or data.get("language"))
    python = os.environ.get("KEYMASTER_PYTHON") or data.get("python") or sys.executable
    core = os.environ.get("KEYMASTER_CORE") or data.get("core") or None
    return Resolved(language=language, python=str(python), core=str(core) if core else None)


def core_problem(resolved: Resolved) -> str | None:
    if not resolved.core or not (Path(resolved.core) / "keymaster").is_dir():
        return "core"
    if not Path(resolved.python).is_file():
        return "python"
    return None
