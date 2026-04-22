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
    def session_exists(self, session_name: str) -> bool: ...

    @abstractmethod
    def select_window(self, target: str) -> bool: ...

    @abstractmethod
    def attach_session(self, session_name: str, *, env: dict[str, str] | None = None) -> int: ...

    @abstractmethod
    def kill_session(self, session_name: str) -> bool: ...


__all__ = ['MuxBackend']
