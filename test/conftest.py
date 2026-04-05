from __future__ import annotations

import sys
from pathlib import Path


def pytest_configure() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    lib_dir = repo_root / "lib"
    sys.path.insert(0, str(lib_dir))

