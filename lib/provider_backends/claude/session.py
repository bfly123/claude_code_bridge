from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from terminal_runtime.backend_env import apply_backend_env
from provider_core.contracts import ProviderSessionBinding
from provider_core.pathing import find_session_file_for_work_dir, session_filename_for_instance
from project_id import compute_ccb_project_id, compute_worktree_scope_id
from terminal_runtime import get_backend_for_session

from .resolver import resolve_claude_session
from .session_runtime import (
    attach_pane_log as _attach_pane_log_impl,
    ensure_pane as _ensure_pane_impl,
    ensure_work_dir_fields as _ensure_work_dir_fields,
    maybe_auto_extract_old_session as _maybe_auto_extract_old_session,
    normalize_legacy_session_data as _normalize_legacy_session_data,
    update_claude_binding as _update_claude_binding_impl,
    write_back as _write_back_impl,
)

apply_backend_env()


@dataclass
class ClaudeProjectSession:
    session_file: Path
    data: dict
    @property
    def terminal(self) -> str:
        return (self.data.get("terminal") or "tmux").strip() or "tmux"

    @property
    def pane_id(self) -> str:
        v = self.data.get("pane_id")
        if not v and self.terminal == "tmux":
            v = self.data.get("tmux_session")
        return str(v or "").strip()

    @property
    def pane_title_marker(self) -> str:
        return str(self.data.get("pane_title_marker") or "").strip()

    @property
    def claude_session_id(self) -> str:
        return str(self.data.get("claude_session_id") or "").strip()

    @property
    def claude_session_path(self) -> str:
        return str(self.data.get("claude_session_path") or "").strip()

    @property
    def work_dir(self) -> str:
        return str(self.data.get("work_dir") or self.session_file.parent)

    @property
    def runtime_dir(self) -> Path:
        return Path(self.data.get("runtime_dir") or self.session_file.parent)

    @property
    def start_cmd(self) -> str:
        return str(self.data.get("start_cmd") or "").strip()

    def user_option_lookup(self) -> dict[str, str]:
        lookup: dict[str, str] = {}
        agent_name = str(self.data.get("agent_name") or "").strip()
        if agent_name:
            lookup["@ccb_agent"] = agent_name
        project_id = str(self.data.get("ccb_project_id") or "").strip()
        if project_id:
            lookup["@ccb_project_id"] = project_id
        return lookup

    def backend(self):
        return get_backend_for_session(self.data)

    def _attach_pane_log(self, backend: object, pane_id: str) -> None:
        _attach_pane_log_impl(self, backend, pane_id)

    def ensure_pane(self) -> Tuple[bool, str]:
        return _ensure_pane_impl(self)

    def update_claude_binding(self, *, session_path: Optional[Path], session_id: Optional[str]) -> None:
        _update_claude_binding_impl(self, session_path=session_path, session_id=session_id)

    def _write_back(self) -> None:
        _normalize_legacy_session_data(self.data)
        _write_back_impl(self)


def _build_session(
    *,
    session_file: Path,
    data: dict,
    fallback_work_dir: Path,
) -> ClaudeProjectSession:
    data.setdefault("work_dir", str(fallback_work_dir))
    if not data.get("ccb_project_id"):
        try:
            data["ccb_project_id"] = compute_ccb_project_id(Path(data.get("work_dir") or fallback_work_dir))
        except Exception:
            pass
    _ensure_work_dir_fields(data, session_file=session_file, fallback_work_dir=fallback_work_dir)
    migrated = _normalize_legacy_session_data(data)
    session = ClaudeProjectSession(session_file=session_file, data=data)
    if migrated:
        session._write_back()
    return session


def find_project_session_file(work_dir: Path, instance: Optional[str] = None) -> Optional[Path]:
    filename = session_filename_for_instance(".claude-session", instance)
    return find_session_file_for_work_dir(work_dir, filename)


def load_project_session(work_dir: Path, instance: Optional[str] = None) -> Optional[ClaudeProjectSession]:
    # Named agents must bind only to their own instance-scoped session file.
    # Falling back to the primary session incorrectly aliases agent runtimes.
    if instance:
        session_file = find_project_session_file(work_dir, instance)
        if not session_file:
            return None
        try:
            raw = session_file.read_text(encoding="utf-8-sig")
            data = json.loads(raw)
            if not isinstance(data, dict) or not data:
                return None
        except Exception:
            return None
        return _build_session(session_file=session_file, data=data, fallback_work_dir=work_dir)

    session_file = find_project_session_file(work_dir)
    if session_file:
        try:
            raw = session_file.read_text(encoding="utf-8-sig")
            data = json.loads(raw)
            if isinstance(data, dict) and data:
                return _build_session(session_file=session_file, data=data, fallback_work_dir=work_dir)
        except Exception:
            pass

    # Fallback: support explicit CCB_SESSION_FILE when the caller is outside the project tree.
    resolution = resolve_claude_session(work_dir)
    if not resolution:
        return None
    data = dict(resolution.data or {})
    if not data:
        return None
    data.setdefault("work_dir", str(work_dir))
    if not data.get("ccb_project_id"):
        try:
            data["ccb_project_id"] = compute_ccb_project_id(Path(data.get("work_dir") or work_dir))
        except Exception:
            pass
    session_file = resolution.session_file
    if not session_file:
        try:
            from provider_sessions.files import project_config_dir

            session_file = project_config_dir(work_dir) / ".claude-session"
        except Exception:
            session_file = None
    if not session_file:
        return None
    return _build_session(session_file=session_file, data=data, fallback_work_dir=work_dir)


def compute_session_key(session: ClaudeProjectSession, instance: Optional[str] = None) -> str:
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
    prefix = "claude"
    if instance:
        prefix = f"claude:{instance}"
    if pid and worktree_scope:
        return f"{prefix}:{pid}:{worktree_scope}"
    if pid:
        return f"{prefix}:{pid}"
    if worktree_scope:
        return f"{prefix}:unknown:{worktree_scope}"
    return f"{prefix}:unknown"


def build_session_binding() -> ProviderSessionBinding:
    return ProviderSessionBinding(
        provider='claude',
        load_session=load_project_session,
        session_id_attr='claude_session_id',
        session_path_attr='claude_session_path',
    )


__all__ = [
    'ClaudeProjectSession',
    'build_session_binding',
    'compute_session_key',
    'find_project_session_file',
    'load_project_session',
]
