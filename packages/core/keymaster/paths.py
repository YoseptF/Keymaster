from __future__ import annotations

import sys
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parents[1]
UPSTREAM_DIR = CORE_DIR / "upstream"
I18N_DIR = CORE_DIR / "i18n"


def add_upstream_to_path(upstream: Path) -> None:
    entry = str(upstream)
    if entry not in sys.path:
        sys.path.insert(0, entry)
