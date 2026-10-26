from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keymaster import cli, paths
from tests import fake_runtime, fakes

fakes.install_modules(cuda=os.environ.get("FAKE_CUDA", "1") == "1")
paths.UPSTREAM_DIR = Path(os.environ["FAKE_UPSTREAM"])
fake_runtime.WINDOW_DELAY = float(os.environ.get("FAKE_WINDOW_DELAY", "0"))
sys.exit(cli.main())
