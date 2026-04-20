from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class TmuxLayoutBackend(Protocol):
    def get_current_pane_id(self) -> str: ...
    def is_alive(self, pane_id: str) -> bool: ...
    def create_pane(
        self,
        cmd: str,
        cwd: str,
        direction: str = 'right',
        percent: int = 50,
        parent_pane: str | None = None,
    ) -> str: ...
    def split_pane(self, parent_pane_id: str, direction: str, percent: int) -> str: ...
    def set_pane_title(self, pane_id: str, title: str) -> None: ...
    def _tmux_run(
        self,
        args: list[str],
        *,
        check: bool = False,
        capture: bool = False,
        input_bytes: bytes | None = None,
        timeout: float | None = None,
    ): ...


@dataclass(frozen=True)
class LayoutResult:
    panes: dict[str, str]
    root_pane_id: str
    needs_attach: bool
    created_panes: list[str]


__all__ = [
    'LayoutResult',
    'TmuxLayoutBackend',
]
