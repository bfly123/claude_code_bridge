from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..home_layout import current_claude_projects_root

CLAUDE_PROJECTS_ROOT = current_claude_projects_root()


@dataclass
class ClaudeSessionResolution:
    data: dict
    session_file: Path | None
    registry: dict | None
    source: str


__all__ = ["CLAUDE_PROJECTS_ROOT", "ClaudeSessionResolution", "current_claude_projects_root"]
