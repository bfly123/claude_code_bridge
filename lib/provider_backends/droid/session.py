from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from terminal_runtime.backend_env import apply_backend_env
from provider_core.contracts import ProviderSessionBinding
from project_id import compute_ccb_project_id, compute_worktree_scope_id
from terminal_runtime import get_backend_for_session

from .session_runtime import (
    attach_pane_log as _attach_pane_log_impl,
    ensure_pane as _ensure_pane_impl,
    find_project_session_file as _find_project_session_file_impl,
    read_json as _read_json,
    update_droid_binding as _update_droid_binding_impl,
    write_back as _write_back_impl,
)

apply_backend_env()


@dataclass
class DroidProjectSession:
    session_file: Path
    data: dict

    @property
    def terminal(self) -> str:
        return (self.data.get("terminal") or "tmux").strip() or "tmux"

    @property
    def pane_id(self) -> str:
        value = self.data.get("pane_id")
        if not value and self.terminal == "tmux":
            value = self.data.get("tmux_session")
        return str(value or "").strip()

    @property
    def pane_title_marker(self) -> str:
        return str(self.data.get("pane_title_marker") or "").strip()

    @property
    def droid_session_id(self) -> str:
        return str(self.data.get("droid_session_id") or "").strip()

    @property
    def droid_session_path(self) -> str:
        return str(self.data.get("droid_session_path") or "").strip()

    @property
    def work_dir(self) -> str:
        return str(self.data.get("work_dir") or self.session_file.parent)

    @property
    def runtime_dir(self) -> Path:
        return Path(self.data.get("runtime_dir") or self.session_file.parent)

    @property
    def start_cmd(self) -> str:
        return str(self.data.get("start_cmd") or "").strip()

    def backend(self):
        return get_backend_for_session(self.data)

    def _attach_pane_log(self, backend: object, pane_id: str) -> None:
        _attach_pane_log_impl(self, backend, pane_id)

    def ensure_pane(self) -> Tuple[bool, str]:
        return _ensure_pane_impl(self)

    def update_droid_binding(self, *, session_path: Optional[Path], session_id: Optional[str]) -> None:
        _update_droid_binding_impl(self, session_path=session_path, session_id=session_id)

    def _write_back(self) -> None:
        _write_back_impl(self)


def find_project_session_file(work_dir: Path, instance: Optional[str] = None) -> Optional[Path]:
    return _find_project_session_file_impl(work_dir, instance)


def load_project_session(work_dir: Path, instance: Optional[str] = None) -> Optional[DroidProjectSession]:
    session_file = find_project_session_file(work_dir, instance)
    if not session_file:
        return None
    data = _read_json(session_file)
    if not data:
        return None
    if data.get("active") is False:
        return None
    return DroidProjectSession(session_file=session_file, data=data)


def compute_session_key(session: DroidProjectSession, instance: Optional[str] = None) -> str:
    pid = str(session.data.get("ccb_project_id") or "").strip()
    if not pid:
        try:
            pid = compute_ccb_project_id(Path(session.work_dir))
        except Exception:
            pid = ""
    worktree_scope = ""
    try:
        worktree_scope = compute_worktree_scope_id(Path(session.work_dir))
    except Exception:
        worktree_scope = ""
    prefix = "droid"
    if instance:
        prefix = f"droid:{instance}"
    if pid and worktree_scope:
        return f"{prefix}:{pid}:{worktree_scope}"
    if pid:
        return f"{prefix}:{pid}"
    if worktree_scope:
        return f"{prefix}:unknown:{worktree_scope}"
    return f"{prefix}:unknown"


def build_session_binding() -> ProviderSessionBinding:
    return ProviderSessionBinding(
        provider="droid",
        load_session=load_project_session,
        session_id_attr="droid_session_id",
        session_path_attr="droid_session_path",
    )


__all__ = [
    "DroidProjectSession",
    "build_session_binding",
    "compute_session_key",
    "find_project_session_file",
    "load_project_session",
]
