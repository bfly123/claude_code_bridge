from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

CLAUDE_PROJECTS_ROOT = Path(
    os.environ.get("CLAUDE_PROJECTS_ROOT")
    or os.environ.get("CLAUDE_PROJECT_ROOT")
    or (Path.home() / ".claude" / "projects")
).expanduser()


@dataclass
class ClaudeSessionResolution:
    data: dict
    session_file: Path | None
    registry: dict | None
    source: str


__all__ = ["CLAUDE_PROJECTS_ROOT", "ClaudeSessionResolution"]
