from __future__ import annotations

import os
from pathlib import Path


def current_session_root() -> Path:
    return Path(os.environ.get("CODEX_SESSION_ROOT") or (Path.home() / ".codex" / "sessions")).expanduser()


SESSION_ROOT = current_session_root()


__all__ = ["SESSION_ROOT", "current_session_root"]
