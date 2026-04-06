from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPaneAssessment:
    binding: object | None
    session: object | None
    terminal: str | None
    pane_state: str | None
    health: str
