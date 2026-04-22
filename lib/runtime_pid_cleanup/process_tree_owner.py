from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from pathlib import Path
from typing import Protocol


class ProcessTreeOwner(Protocol):
    def terminate(self, pid: int, *, timeout_s: float, is_pid_alive_fn) -> bool: ...


@dataclass(frozen=True)
class ProcessTreeTarget:
    pid: int
    hint_paths: tuple[Path, ...] = ()
    metadata: dict[str, object] | None = None


class ProcessTreeOwnerFactory(Protocol):
    def build(self, target: ProcessTreeTarget) -> ProcessTreeOwner | None: ...


class LocalProcessTreeOwner:
    def __init__(self, terminate_pid_tree_fn: Callable[..., bool]) -> None:
        self._terminate_pid_tree_fn = terminate_pid_tree_fn

    def terminate(self, pid: int, *, timeout_s: float, is_pid_alive_fn) -> bool:
        return self._terminate_pid_tree_fn(pid, timeout_s=timeout_s, is_pid_alive_fn=is_pid_alive_fn)


__all__ = ['LocalProcessTreeOwner', 'ProcessTreeOwner', 'ProcessTreeOwnerFactory', 'ProcessTreeTarget']
