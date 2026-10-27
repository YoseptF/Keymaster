from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANGS = ("en", "es-419")
NSIS_LANGS = {"en": "${LANG_ENGLISH}", "es-419": "${LANG_SPANISHINTERNATIONAL}"}


def load_tables(i18n_dir: Path = HERE / "i18n") -> dict[str, dict[str, str]]:
    return {lang: json.loads((i18n_dir / f"{lang}.json").read_text(encoding="utf-8")) for lang in LANGS}


def load_pins(path: Path = HERE / "pins.json") -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def nsis_string(value: str) -> str:
    out = value.replace("$", "$$").replace('"', '$\\"').replace("\r\n", "\n").replace("\n", "$\\r$\\n").replace("\t", "$\\t")
    return f'"{out}"'


def bash_string(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def nsis_langstrings(tables: dict[str, dict[str, str]]) -> str:
    lines = []
    for key in sorted(tables["en"]):
        for lang in LANGS:
            lines.append(f"LangString {key} {NSIS_LANGS[lang]} {nsis_string(tables[lang][key])}")
    return "\n".join(lines) + "\n"


def nsis_defines(values: dict[str, str]) -> str:
    return "".join(f"!define {name} {nsis_string(str(value))}\n" for name, value in values.items())


def bash_messages(tables: dict[str, dict[str, str]]) -> str:
    lines = ["declare -A KM_TEXT=("]
    for key in sorted(tables["en"]):
        for lang in LANGS:
            lines.append(f"  [{bash_string(lang + ':' + key)}]={bash_string(tables[lang][key])}")
    lines.append(")")
    return "\n".join(lines) + "\n"


def bash_vars(values: dict[str, str]) -> str:
    return "".join(f"{name}={bash_string(str(value))}\n" for name, value in values.items())
