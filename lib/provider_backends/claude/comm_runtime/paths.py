from __future__ import annotations

import os
from pathlib import Path

CLAUDE_PROJECTS_ROOT = Path(
    os.environ.get("CLAUDE_PROJECTS_ROOT")
    or os.environ.get("CLAUDE_PROJECT_ROOT")
    or (Path.home() / ".claude" / "projects")
).expanduser()

__all__ = ["CLAUDE_PROJECTS_ROOT"]
