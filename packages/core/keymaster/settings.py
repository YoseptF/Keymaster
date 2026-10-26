from __future__ import annotations

import json
import os
import sys
from pathlib import Path

LANGUAGES = ("en", "es-419")
DEFAULT_LANGUAGE = "en"
KEYS = ("language", "python", "core")
ENV_OVERRIDES = (("python", "KEYMASTER_PYTHON"), ("core", "KEYMASTER_CORE"), ("language", "KEYMASTER_LANGUAGE"))


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


def normalize_language(value) -> str:
    return value if value in LANGUAGES else DEFAULT_LANGUAGE


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
    data["language"] = normalize_language(data.get("language"))
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
