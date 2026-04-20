from __future__ import annotations

import os
from pathlib import Path


def ensure_log_reader(comm, *, log_reader_cls) -> None:
    if comm._log_reader is not None:
        return
    work_dir_hint = comm.session_info.get("work_dir")
    log_work_dir = Path(work_dir_hint) if isinstance(work_dir_hint, str) and work_dir_hint else None
    projects_root_hint = comm.session_info.get("claude_projects_root")
    log_root = Path(projects_root_hint).expanduser() if isinstance(projects_root_hint, str) and projects_root_hint else None
    include_subagents = os.environ.get("CLAUDE_LOG_INCLUDE_SUBAGENTS", "").strip().lower() in ("1", "true", "yes")
    include_subagent_user = os.environ.get("CLAUDE_LOG_INCLUDE_SUBAGENT_USER", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    subagent_tag = os.environ.get("CLAUDE_LOG_SUBAGENT_TAG", "[subagent]")
    comm._log_reader = log_reader_cls(
        root=log_root,
        work_dir=log_work_dir,
        include_subagents=include_subagents,
        include_subagent_user=include_subagent_user,
        subagent_tag=subagent_tag,
    )
    preferred_session = comm.session_info.get("claude_session_path")
    if preferred_session:
        comm._log_reader.set_preferred_session(Path(str(preferred_session)))
    if not comm._log_reader_primed:
        comm._prime_log_binding()
        comm._log_reader_primed = True


def prime_log_binding(comm) -> None:
    session_path = comm.log_reader.current_session_path()
    if not session_path:
        return
    comm._remember_claude_session(session_path)


def remember_claude_session(
    comm,
    session_path: Path,
    *,
    remember_claude_session_binding_fn,
) -> None:
    if not comm.project_session_file or not session_path or not isinstance(session_path, Path):
        return
    data = remember_claude_session_binding_fn(
        project_session_file=Path(comm.project_session_file),
        session_path=session_path,
        session_info=comm.session_info,
    )
    if data is None:
        return
    comm.session_info["work_dir"] = str(data.get("work_dir") or comm.session_info.get("work_dir") or "")
    comm.session_info["work_dir_norm"] = str(data.get("work_dir_norm") or "")
    comm.session_info["claude_session_path"] = str(data.get("claude_session_path") or "")
    if session_path.stem and comm.session_info.get("claude_session_id") != session_path.stem:
        comm.session_info["claude_session_id"] = session_path.stem
    comm._publish_registry()


def publish_registry(comm, *, publish_claude_registry_fn) -> None:
    publish_claude_registry_fn(
        session_info=comm.session_info,
        terminal=comm.terminal,
        pane_id=comm.pane_id or None,
        project_session_file=comm.project_session_file,
    )


__all__ = [
    "ensure_log_reader",
    "prime_log_binding",
    "publish_registry",
    "remember_claude_session",
]
