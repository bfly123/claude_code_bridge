from __future__ import annotations

import os
from pathlib import Path

SESSION_ROOT = Path(os.environ.get("CODEX_SESSION_ROOT") or (Path.home() / ".codex" / "sessions")).expanduser()

__all__ = ["SESSION_ROOT"]
