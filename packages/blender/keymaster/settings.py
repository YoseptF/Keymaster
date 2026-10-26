from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

LANGUAGES = ("en", "es-419")
DEFAULT_LANGUAGE = "en"


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


def write_value(path: Path, key: str, value) -> dict:
    path = Path(path)
    data = read(path)
    data[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".settings-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return data


def normalize_language(value) -> str:
    return value if value in LANGUAGES else DEFAULT_LANGUAGE


def resolve(env: Optional[Mapping[str, str]] = None, platform: Optional[str] = None) -> Resolved:
    env = os.environ if env is None else env
    path = settings_path(env, platform)
    data = read(path)
    python = env.get("KEYMASTER_PYTHON") or data.get("python") or None
    core = env.get("KEYMASTER_CORE") or data.get("core") or None
    language = normalize_language(env.get("KEYMASTER_LANGUAGE") or data.get("language"))
    return Resolved(python=python, core=core, language=language, path=path)


def file_language(env: Optional[Mapping[str, str]] = None, platform: Optional[str] = None) -> str:
    return normalize_language(read(settings_path(env, platform)).get("language"))


def set_language(language: str, env: Optional[Mapping[str, str]] = None, platform: Optional[str] = None) -> Path:
    path = settings_path(env, platform)
    write_value(path, "language", normalize_language(language))
    return path
