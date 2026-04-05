from __future__ import annotations

import os
from pathlib import Path

GEMINI_ROOT = Path(os.environ.get("GEMINI_ROOT") or (Path.home() / ".gemini" / "tmp")).expanduser()

__all__ = ["GEMINI_ROOT"]
