"""
Base provider adapter interface for the unified ask daemon.
"""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol, TypeVar

from providers import ProviderDaemonSpec


@dataclass
class ProviderRequest:
    """Unified request structure for all providers."""
    client_id: str
    work_dir: str
    timeout_s: float
    quiet: bool
    message: str
    output_path: Optional[str] = None
    req_id: Optional[str] = None
    caller: str = "claude"
    no_wrap: bool = False


@dataclass
class ProviderResult:
    """Unified result structure for all providers."""
    exit_code: int
    reply: str
    req_id: str
    session_key: str
    done_seen: bool
    done_ms: Optional[int] = None
    anchor_seen: bool = False
    anchor_ms: Optional[int] = None
    fallback_scan: bool = False
    log_path: Optional[str] = None
    extra: Optional[dict] = None


class QueuedTaskLike(Protocol):
    """Protocol for queued tasks."""
    req_id: str
    done_event: threading.Event
    result: Optional[ProviderResult]


@dataclass
class QueuedTask:
    """A task queued for processing by a provider adapter."""
    request: ProviderRequest
    created_ms: int
    req_id: str
    done_event: threading.Event
    result: Optional[ProviderResult] = None


class BaseProviderAdapter(ABC):
    """
    Abstract base class for provider adapters.

    Each provider (codex, gemini, opencode, droid, claude) implements
    this interface to integrate with the unified daemon.
    """

    @property
    @abstractmethod
    def key(self) -> str:
        """Provider key (e.g., 'codex', 'gemini', 'opencode', 'droid', 'claude')."""
        ...

    @property
    @abstractmethod
    def spec(self) -> ProviderDaemonSpec:
        """Provider daemon specification."""
        ...

    @property
    @abstractmethod
    def session_filename(self) -> str:
        """Session file name (e.g., '.codex-session')."""
        ...

    @abstractmethod
    def load_session(self, work_dir: Path) -> Optional[Any]:
        """Load session for the given work directory."""
        ...

    @abstractmethod
    def compute_session_key(self, session: Any) -> str:
        """Compute a unique session key for routing."""
        ...

    @abstractmethod
    def handle_task(self, task: QueuedTask) -> ProviderResult:
        """
        Handle a queued task and return the result.

        This is the main entry point for processing requests.
        """
        ...

    def handle_exception(self, exc: Exception, task: QueuedTask) -> ProviderResult:
        """Handle an exception during task processing."""
        return ProviderResult(
            exit_code=1,
            reply=str(exc),
            req_id=task.req_id,
            session_key=f"{self.key}:unknown",
            done_seen=False,
        )

    def on_start(self) -> None:
        """Called when the daemon starts. Override for initialization."""
        pass

    def on_stop(self) -> None:
        """Called when the daemon stops. Override for cleanup."""
        pass
