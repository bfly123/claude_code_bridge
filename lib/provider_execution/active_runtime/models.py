from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PreparedActiveStart:
    work_dir: Path
    session: object
    pane_id: str
    backend: object


@dataclass(frozen=True)
class PreparedActivePoll:
    reader: object
    backend: object
    pane_id: str


__all__ = ["PreparedActivePoll", "PreparedActiveStart"]
