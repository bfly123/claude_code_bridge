from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class TerminalBackend(ABC):
    @abstractmethod
    def send_text(self, pane_id: str, text: str) -> None: ...

    @abstractmethod
    def is_alive(self, pane_id: str) -> bool: ...

    @abstractmethod
    def kill_pane(self, pane_id: str) -> None: ...

    @abstractmethod
    def activate(self, pane_id: str) -> None: ...

    @abstractmethod
    def create_pane(
        self,
        cmd: str,
        cwd: str,
        direction: str = "right",
        percent: int = 50,
        parent_pane: Optional[str] = None,
    ) -> str: ...
