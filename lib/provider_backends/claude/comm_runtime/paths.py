from __future__ import annotations

from ..home_layout import current_claude_projects_root

CLAUDE_PROJECTS_ROOT = current_claude_projects_root()

__all__ = ["CLAUDE_PROJECTS_ROOT", "current_claude_projects_root"]
