from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from provider_core.contracts import ProviderSessionBinding
from provider_core.pathing import find_session_file_for_work_dir, session_filename_for_instance
from project.identity import compute_ccb_project_id, compute_worktree_scope_id
from provider_sessions.files import safe_write_session

from .lifecycle import attach_pane_log as attach_pane_log_impl
from .lifecycle import ensure_pane as ensure_pane_impl


def find_project_session_file_for_provider(
    work_dir: Path,
    *,
    session_filename: str,
    instance: Optional[str] = None,
) -> Optional[Path]:
    filename = session_filename_for_instance(session_filename, instance)
    return find_session_file_for_work_dir(work_dir, filename)


def read_session_json(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8-sig")
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def session_tmux_identity_lookup(data: dict) -> dict[str, str]:
    lookup: dict[str, str] = {}
    agent_name = str(data.get("agent_name") or "").strip()
    if agent_name:
        lookup["@ccb_agent"] = agent_name
    project_id = str(data.get("ccb_project_id") or "").strip()
    if project_id:
        lookup["@ccb_project_id"] = project_id
    slot_key = str(data.get("ccb_slot") or "").strip()
    if slot_key:
        lookup["@ccb_slot"] = slot_key
    managed_by = str(data.get("ccb_managed_by") or "").strip()
    if managed_by:
        lookup["@ccb_managed_by"] = managed_by
    return lookup


@dataclass
class PaneLogProjectSessionBase:
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
    def work_dir(self) -> str:
        return str(self.data.get("work_dir") or self.session_file.parent)

    @property
    def runtime_dir(self) -> Path:
        return Path(self.data.get("runtime_dir") or self.session_file.parent)

    @property
    def start_cmd(self) -> str:
        return str(self.data.get("start_cmd") or "").strip()

    def user_option_lookup(self) -> dict[str, str]:
        return session_tmux_identity_lookup(self.data)

    def _attach_pane_log(self, backend: object, pane_id: str) -> None:
        attach_pane_log_impl(self, backend, pane_id)

    def ensure_pane(self) -> Tuple[bool, str]:
        return ensure_pane_impl(self, now_str_fn=now_str, attach_pane_log_fn=attach_pane_log_impl)

    def _write_back(self) -> None:
        payload = json.dumps(self.data, ensure_ascii=False, indent=2) + "\n"
        safe_write_session(self.session_file, payload)


def load_project_session_for_provider(
    work_dir: Path,
    *,
    session_filename: str,
    session_cls,
    instance: Optional[str] = None,
):
    session_file = find_project_session_file_for_provider(
        work_dir,
        session_filename=session_filename,
        instance=instance,
    )
    if not session_file:
        return None
    data = read_session_json(session_file)
    if not data:
        return None
    if data.get("active") is False:
        return None
    return session_cls(session_file=session_file, data=data)


def compute_session_key_for_provider(session, *, provider: str, instance: Optional[str] = None) -> str:
    work_dir = Path(session.work_dir)
    pid = _resolved_project_id(session, work_dir)
    worktree_scope = _resolved_worktree_scope(work_dir)
    return _session_key(
        _session_key_prefix(provider, instance=instance),
        project_id=pid,
        worktree_scope=worktree_scope,
    )


def _resolved_project_id(session, work_dir: Path) -> str:
    pid = str(session.data.get("ccb_project_id") or "").strip()
    if pid:
        return pid
    try:
        return compute_ccb_project_id(work_dir)
    except Exception:
        return ""


def _resolved_worktree_scope(work_dir: Path) -> str:
    try:
        return compute_worktree_scope_id(work_dir)
    except Exception:
        return ""


def _session_key_prefix(provider: str, *, instance: Optional[str]) -> str:
    if instance:
        return f"{provider}:{instance}"
    return provider


def _session_key(prefix: str, *, project_id: str, worktree_scope: str) -> str:
    if project_id and worktree_scope:
        return f"{prefix}:{project_id}:{worktree_scope}"
    if project_id:
        return f"{prefix}:{project_id}"
    if worktree_scope:
        return f"{prefix}:unknown:{worktree_scope}"
    return f"{prefix}:unknown"


def build_session_binding_for_provider(*, provider: str, load_session) -> ProviderSessionBinding:
    return ProviderSessionBinding(
        provider=provider,
        load_session=load_session,
        session_id_attr=f"{provider}_session_id",
        session_path_attr=f"{provider}_session_path",
    )


__all__ = [
    "PaneLogProjectSessionBase",
    "build_session_binding_for_provider",
    "compute_session_key_for_provider",
    "find_project_session_file_for_provider",
    "load_project_session_for_provider",
    "now_str",
    "read_session_json",
    "session_tmux_identity_lookup",
]
