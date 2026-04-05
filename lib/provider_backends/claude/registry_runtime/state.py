from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from provider_backends.claude.session import ClaudeProjectSession
from provider_sessions.watch import SessionFileWatcher


@dataclass
class SessionEntry:
    work_dir: Path
    session: Optional[ClaudeProjectSession]
    session_file: Optional[Path] = None
    file_mtime: float = 0.0
    last_check: float = 0.0
    valid: bool = False
    next_bind_refresh: float = 0.0
    bind_backoff_s: float = 0.0


@dataclass
class WatcherEntry:
    watcher: SessionFileWatcher
    keys: set[str] = field(default_factory=set)
