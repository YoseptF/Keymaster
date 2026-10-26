#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ROOT / "packages"
LANGS = ("en", "es-419")
CODE_SUFFIXES = {".py", ".js", ".jsx", ".mjs", ".html", ".cpp", ".h", ".hpp", ".sh", ".ps1"}
SKIP_DIRS = {"node_modules", "__pycache__", "tests", "testing", "upstream", "build", "dist", ".venv", "venv"}
SKIP_FILES = {"build.py"}

KEY = r"""["']([a-z0-9_]+(?:\.[a-z0-9_]+)+)["']"""
KEY_USES = [
    re.compile(r"""\bt\(\s*""" + KEY),
    re.compile(r"""\btr\(\s*""" + KEY),
    re.compile(r"""data-i18n(?:-[a-z]+)?=""" + KEY),
    re.compile(r"""\bmessage_key["']?\s*[:=]\s*""" + KEY),
    re.compile(r"""\b(?:say|msg)\s+""" + KEY),
]
PLACEHOLDER = re.compile(r"\{([a-zA-Z0-9_]+)\}")
WORDY = r"""["'][^"'\n]*[A-Za-z]{2}[^"'\n]*["']"""

HARDCODED = {
    ".py": [
        re.compile(r"""\b(?:text|description|bl_label|bl_description|title|label|tooltip|placeholder)\s*=\s*""" + WORDY),
        re.compile(r"""\b(?:setText|setWindowTitle|setToolTip|setPlaceholderText|addItem|setStatusTip)\(\s*""" + WORDY),
        re.compile(r"""\bQ(?:Label|PushButton|CheckBox|GroupBox|Action|RadioButton)\(\s*""" + WORDY),
        re.compile(r"""\bQMessageBox\.\w+\([^)]*?""" + WORDY),
        re.compile(r"""\b(?:setTitle|setHeaderLabels|setTabText|setItemText|setSuffix|setPrefix|setSpecialValueText|setInformativeText|setDetailedText|setLabelText|setWhatsThis)\(\s*\[?\s*""" + WORDY),
        re.compile(r"""\b(?:setItemText|setTabText|insertItem|addTab)\(\s*[\w.]+\s*,\s*""" + WORDY),
        re.compile(r"""\bQ(?:Menu|ListWidgetItem|TableWidgetItem|StandardItem|ToolButton|CommandLinkButton)\(\s*""" + WORDY),
        re.compile(r"""\bQ(?:FileDialog\.get\w+|InputDialog\.get\w+)\(\s*[\w.]+\s*,\s*""" + WORDY),
        re.compile(r"""\bself\.report\(\s*\{[^}]*\}\s*,\s*""" + WORDY),
        re.compile(r"""\b(?:bl_category|heading|confirm_text)\s*=\s*""" + WORDY),
        re.compile(r"""\b(?:Bool|Int|Float|String|Enum|Pointer|Collection)(?:Vector)?Property\([^)]*?\bname\s*=\s*""" + WORDY),
        re.compile(r"""\bitems\s*=\s*[\[(]\s*\(\s*["'][^"'\n]*["']\s*,\s*""" + WORDY),
        re.compile(r"""\bpoll_message_set\(\s*""" + WORDY),
    ],
    ".js": [
        re.compile(r"""\.(?:textContent|innerText|title|placeholder)\s*=\s*["'`][^"'`\n]*[A-Za-z]{2}"""),
        re.compile(r"""\balert\(\s*""" + WORDY),
        re.compile(r"""\b(?:confirm|prompt)\(\s*""" + WORDY),
        re.compile(r"""\.innerHTML\s*=\s*["'`][^"'`\n]*[A-Za-z]{2}"""),
        re.compile(r"""\.setAttribute\(\s*["'](?:title|placeholder|aria-label|alt)["']\s*,\s*""" + WORDY),
    ],
    ".jsx": [
        re.compile(r"""\balert\(\s*""" + WORDY),
        re.compile(r"""\b(?:confirm|prompt)\(\s*""" + WORDY),
        re.compile(r"""\bnew\s+Window\(\s*["'][^"']*["']\s*,\s*""" + WORDY),
        re.compile(r"""\.add\(\s*["'](?:statictext|button|checkbox|radiobutton|panel|edittext)["']\s*,\s*(?:\[[^\]]*\]|[^,()\[]*)\s*,\s*""" + WORDY),
    ],
    ".html": [
        re.compile(r""">\s*[^<>{}\s][^<>{}]*[A-Za-z]{2}[^<>{}]*<"""),
        re.compile(r"""(?<![\w-])(?:title|placeholder|aria-label|alt)=["'][^"']*[A-Za-z]{2}[^"']*["']"""),
    ],
    ".cpp": [
        re.compile(r"""\bset(?:Label|Labels|Hint|ScriptName)\(\s*"[^"\n]*[A-Za-z]{2}"""),
        re.compile(r"""\bsendMessage\([^;]*?"[^"\n]*[A-Za-z]{2}"""),
    ],
}


def load(table_dir: Path, lang: str, errors: list[str]) -> dict[str, str]:
    path = table_dir / f"{lang}.json"
    if not path.is_file():
        errors.append(f"{path.relative_to(ROOT)} is missing")
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(isinstance(v, str) for v in data.values()):
        errors.append(f"{path.relative_to(ROOT)} must be a flat object of strings")
        return {}
    return data


def code_files(pkg: Path):
    for path in sorted(pkg.rglob("*")):
        rel = path.relative_to(pkg)
        if (path.is_file() and path.suffix in CODE_SUFFIXES and path.name not in SKIP_FILES
                and not SKIP_DIRS & set(rel.parts[:-1])):
            yield path


def check_tables(pkg: Path, errors: list[str]) -> dict[str, str]:
    table_dir = pkg / "i18n"
    tables = {lang: load(table_dir, lang, errors) for lang in LANGS}
    base = tables["en"]
    name = pkg.relative_to(ROOT).as_posix()
    for lang, table in tables.items():
        for key in sorted(set(base) - set(table)):
            errors.append(f"{name}/i18n/{lang}.json is missing {key}")
        for key in sorted(set(table) - set(base)):
            errors.append(f"{name}/i18n/{lang}.json has {key}, which en.json lacks")
        for key, value in table.items():
            if not value.strip():
                errors.append(f"{name}/i18n/{lang}.json: {key} is empty")
            if key in base and set(PLACEHOLDER.findall(value)) != set(PLACEHOLDER.findall(base[key])):
                errors.append(f"{name}/i18n/{lang}.json: {key} placeholders differ from en.json")
        for key in table:
            if not key.startswith(f"{pkg.name}."):
                errors.append(f"{name}/i18n/{lang}.json: {key} must start with '{pkg.name}.'")
    return base


def main() -> int:
    errors: list[str] = []
    pkgs = sorted(p for p in PACKAGES.iterdir() if (p / "package.json").is_file())
    defined: dict[str, str] = {}
    used: set[str] = set()
    for pkg in pkgs:
        defined.update(check_tables(pkg, errors))
        allow_file = pkg / "i18n" / "allow.txt"
        allowed = set()
        if allow_file.is_file():
            allowed = {line.strip() for line in allow_file.read_text(encoding="utf-8").splitlines() if line.strip()}
        for path in code_files(pkg):
            rel = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in KEY_USES:
                used.update(pattern.findall(text))
            for pattern in HARDCODED.get(path.suffix, []):
                for match in pattern.finditer(text):
                    snippet = match.group(0).strip()
                    if f"{path.relative_to(pkg).as_posix()}: {snippet}" in allowed:
                        continue
                    line = text.count("\n", 0, match.start()) + 1
                    errors.append(f"{rel}:{line}: user-facing text must go through i18n: {snippet[:80]}")
        for doc in sorted(pkg.glob("README.md")):
            if not doc.with_name("README.es-419.md").is_file():
                errors.append(f"{doc.relative_to(ROOT)} has no README.es-419.md next to it")

    for key in sorted(used - set(defined)):
        errors.append(f"key used in code but missing from every i18n/en.json: {key}")
    for key in sorted(set(defined) - used):
        errors.append(f"key defined but never used: {key}")
    if not (ROOT / "README.es-419.md").is_file():
        errors.append("README.md has no README.es-419.md next to it")

    for error in errors:
        print(f"::error::{error}")
    if errors:
        print(f"{len(errors)} i18n problem(s)")
        return 1
    print(f"i18n ok: {len(defined)} keys in {', '.join(LANGS)} across {len(pkgs)} package(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
