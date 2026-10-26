import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
FAKE_CORE = ROOT / "packages" / "core" / "testing" / "fake_core"

if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))


def scratch() -> tempfile.TemporaryDirectory:
    base = ROOT / "tmp" / "unit"
    base.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=base)


def env(**extra) -> dict:
    base = {k: v for k, v in os.environ.items() if not k.startswith("KEYMASTER_")}
    base.update(extra)
    return base
