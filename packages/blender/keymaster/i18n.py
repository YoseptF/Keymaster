from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Callable, Iterable, Optional

from . import settings

HERE = Path(__file__).resolve().parent
REFRESH_SECONDS = 1.0
PLACEHOLDER = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def table_dirs(here: Path = HERE) -> list[Path]:
    bundled = here / "i18n"
    if (bundled / "en.json").is_file():
        return [bundled, bundled / "core"]
    return [here.parent / "i18n", here.parents[1] / "core" / "i18n"]


def load_tables(dirs: Iterable[Path]) -> dict[str, dict[str, str]]:
    tables: dict[str, dict[str, str]] = {lang: {} for lang in settings.LANGUAGES}
    for directory in dirs:
        for lang in settings.LANGUAGES:
            try:
                data = json.loads((Path(directory) / f"{lang}.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict):
                tables[lang].update({k: v for k, v in data.items() if isinstance(v, str)})
    return tables


def fill(text: str, params: Optional[dict]) -> str:
    if not params:
        return text
    return PLACEHOLDER.sub(lambda m: str(params[m.group(1)]) if m.group(1) in params else m.group(0), text)


class Translator:
    def __init__(self, dirs: Optional[Iterable[Path]] = None, language: Optional[Callable[[], str]] = None,
                 clock: Callable[[], float] = time.monotonic):
        self._dirs = list(dirs) if dirs is not None else None
        self._language_source = language or (lambda: settings.resolve().language)
        self._clock = clock
        self._tables: Optional[dict[str, dict[str, str]]] = None
        self._language = settings.DEFAULT_LANGUAGE
        self._checked: Optional[float] = None

    @property
    def tables(self) -> dict[str, dict[str, str]]:
        if self._tables is None:
            self._tables = load_tables(self._dirs if self._dirs is not None else table_dirs())
        return self._tables

    def language(self) -> str:
        now = self._clock()
        if self._checked is None or now - self._checked >= REFRESH_SECONDS:
            self._language = settings.normalize_language(self._language_source())
            self._checked = now
        return self._language

    def invalidate(self) -> None:
        self._checked = None

    def lookup(self, key: str) -> Optional[str]:
        tables = self.tables
        return tables[self.language()].get(key) or tables[settings.DEFAULT_LANGUAGE].get(key)

    def has(self, key: Optional[str]) -> bool:
        return bool(key) and self.lookup(key) is not None

    def translate(self, key: Optional[str], params: Optional[dict] = None) -> str:
        text = self.lookup(key) if key else None
        return fill(text, params) if text is not None else (key or "")

    def __call__(self, key: str, **params) -> str:
        return self.translate(key, params)


translator = Translator()


def t(key: str, **params) -> str:
    return translator(key, **params)
