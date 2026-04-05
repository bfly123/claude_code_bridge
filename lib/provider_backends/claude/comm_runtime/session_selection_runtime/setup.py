from __future__ import annotations

import os
from pathlib import Path


def initialize_reader(
    reader,
    *,
    root: Path,
    work_dir: Path | None,
    use_sessions_index: bool,
    include_subagents: bool,
    include_subagent_user: bool,
    subagent_tag: str,
) -> None:
    reader.root = Path(root).expanduser()
    reader.work_dir = work_dir or Path.cwd()
    reader._preferred_session = None
    reader._use_sessions_index = bool(use_sessions_index)
    reader._include_subagents = bool(include_subagents)
    reader._include_subagent_user = bool(include_subagent_user)
    reader._subagent_tag = str(subagent_tag or "").strip()
    try:
        poll = float(os.environ.get("CLAUDE_POLL_INTERVAL", "0.05"))
    except Exception:
        poll = 0.05
    reader._poll_interval = min(0.5, max(0.02, poll))


__all__ = ["initialize_reader"]
