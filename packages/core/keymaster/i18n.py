from __future__ import annotations

import json
import string

from . import paths, settings

_tables: dict[str, dict] = {}


class _Params(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def table(lang: str) -> dict:
    if lang not in _tables:
        try:
            _tables[lang] = json.loads((paths.I18N_DIR / f"{lang}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _tables[lang] = {}
    return _tables[lang]


def current_language() -> str:
    return settings.effective()["language"]


def t(key: str, params: dict | None = None, lang: str | None = None) -> str:
    lang = settings.normalize_language(lang) if lang else current_language()
    text = table(lang).get(key) or table(settings.DEFAULT_LANGUAGE).get(key) or key
    values = _Params({k: _show(v) for k, v in (params or {}).items()})
    return string.Formatter().vformat(text, (), values)


def _show(value) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value)
