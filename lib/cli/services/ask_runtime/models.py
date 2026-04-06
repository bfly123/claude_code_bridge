from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AskSummary:
    project_id: str
    submission_id: str | None
    jobs: tuple[dict, ...]


__all__ = ['AskSummary']
