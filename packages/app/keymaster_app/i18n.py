from __future__ import annotations

import json
from pathlib import Path

from keymaster_app import APP_ROOT
from keymaster_app.settings import DEFAULT_LANGUAGE, normalize_language


class _Params(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _read(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


class Translator:
    def __init__(self, language: str = DEFAULT_LANGUAGE, core_dir: str | None = None, app_root: Path = APP_ROOT):
        self.app_root = Path(app_root)
        self.core_dir = core_dir
        self.language = DEFAULT_LANGUAGE
        self.table: dict[str, str] = {}
        self.set_language(language)

    def table_dirs(self) -> list[Path]:
        dirs = [self.app_root / "i18n"]
        if self.core_dir:
            dirs.append(Path(self.core_dir) / "i18n")
        dirs.append(self.app_root / "i18n" / "core")
        dirs.append(self.app_root.parent / "core" / "i18n")
        return dirs

    def set_language(self, language: str) -> str:
        self.language = normalize_language(language)
        merged: dict[str, str] = {}
        for lang in dict.fromkeys((DEFAULT_LANGUAGE, self.language)):
            for directory in reversed(self.table_dirs()):
                merged.update(_read(directory / f"{lang}.json"))
        self.table = merged
        return self.language

    def has(self, key: str) -> bool:
        return key in self.table

    def __call__(self, key: str, **params: object) -> str:
        value = self.table.get(key, key)
        if not params:
            return value
        try:
            return value.format_map(_Params({k: str(v) for k, v in params.items()}))
        except (ValueError, IndexError):
            return value


_current = Translator()


def install(translator: Translator) -> Translator:
    global _current
    _current = translator
    return translator


def current() -> Translator:
    return _current


def t(key: str, **params: object) -> str:
    return _current(key, **params)
