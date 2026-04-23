from __future__ import annotations

from abc import ABC, abstractmethod

from .backend_types import TerminalBackend


class MuxBackend(TerminalBackend, ABC):
    @property
    @abstractmethod
    def backend_family(self) -> str: ...

    @property
    @abstractmethod
    def backend_impl(self) -> str: ...

    @property
    @abstractmethod
    def backend_ref(self) -> str | None: ...

    @abstractmethod
    def get_current_pane_id(self) -> str: ...

    @abstractmethod
    def pane_exists(self, pane_id: str) -> bool: ...

    @abstractmethod
    def find_pane_by_title_marker(self, marker: str) -> str | None: ...

    @abstractmethod
    def find_pane_by_user_options(self, expected: dict[str, str]) -> str | None: ...

    @abstractmethod
    def list_panes_by_user_options(self, expected: dict[str, str]) -> list[str]: ...

    @abstractmethod
    def describe_pane(
        self,
        pane_id: str,
        *,
        user_options: tuple[str, ...] = (),
    ) -> dict[str, str] | None: ...

    @abstractmethod
    def get_pane_content(self, pane_id: str, lines: int = 20) -> str | None: ...

    @abstractmethod
    def is_pane_alive(self, pane_id: str) -> bool: ...

    @abstractmethod
    def split_pane(self, parent_pane_id: str, direction: str, percent: int) -> str: ...

    @abstractmethod
    def set_pane_title(self, pane_id: str, title: str) -> None: ...

    @abstractmethod
    def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None: ...

    @abstractmethod
    def set_pane_style(
        self,
        pane_id: str,
        *,
        border_style: str | None = None,
        active_border_style: str | None = None,
    ) -> None: ...

    @abstractmethod
    def send_key(self, pane_id: str, key: str) -> bool: ...

    @abstractmethod
    def respawn_pane(
        self,
        pane_id: str,
        *,
        cmd: str,
        cwd: str | None = None,
        stderr_log_path: str | None = None,
        remain_on_exit: bool = True,
    ) -> None: ...

    @abstractmethod
    def save_crash_log(
        self,
        pane_id: str,
        crash_log_path: str,
        *,
        lines: int = 1000,
    ) -> None: ...

    @abstractmethod
    def session_exists(self, session_name: str) -> bool: ...

    @abstractmethod
    def select_window(self, target: str) -> bool: ...

    @abstractmethod
    def attach_session(self, session_name: str, *, env: dict[str, str] | None = None) -> int: ...

    @abstractmethod
    def kill_session(self, session_name: str) -> bool: ...

    def get_text(self, pane_id: str, lines: int = 20) -> str | None:
        return self.get_pane_content(pane_id, lines=lines)

    def send_text_to_pane(self, pane_id: str, text: str) -> None:
        self.send_text(pane_id, text)

    def is_tmux_pane_alive(self, pane_id: str) -> bool:
        return self.is_pane_alive(pane_id)

    def kill_tmux_pane(self, pane_id: str) -> None:
        self.kill_pane(pane_id)

    def activate_tmux_pane(self, pane_id: str) -> None:
        self.activate(pane_id)


__all__ = ['MuxBackend']
