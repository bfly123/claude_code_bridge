from __future__ import annotations

import json
import time
from pathlib import Path

from provider_core.pathing import session_filename_for_agent
from project.identity import normalize_work_dir
from provider_core.runtime_shared import pane_title_marker as build_pane_title_marker
from provider_sessions.files import safe_write_session


def write_session_file(
    *,
    context,
    spec,
    plan,
    runtime_dir: Path,
    run_cwd: Path,
    pane_id: str,
    tmux_socket_name: str | None,
    tmux_socket_path: str | None,
    pane_title_marker: str,
    start_cmd: str,
    launch_session_id: str,
    provider_payload: dict[str, object],
) -> Path:
    session_path = context.paths.ccb_dir / session_filename(spec)
    payload = {
        "ccb_session_id": launch_session_id,
        "agent_name": spec.name,
        "ccb_project_id": context.project.project_id,
        "runtime_dir": str(runtime_dir),
        "completion_artifact_dir": str(runtime_dir / "completion"),
        "terminal": "tmux",
        "tmux_session": pane_id,
        "pane_id": pane_id,
        "pane_title_marker": pane_title_marker,
        "workspace_path": str(plan.workspace_path),
        "work_dir": str(run_cwd),
        "work_dir_norm": normalize_work_dir(run_cwd),
        "start_dir": str(context.project.project_root),
        "active": True,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "start_cmd": start_cmd,
    }
    if tmux_socket_name:
        payload["tmux_socket_name"] = str(tmux_socket_name)
    if tmux_socket_path:
        payload["tmux_socket_path"] = str(Path(tmux_socket_path).expanduser())
    payload.update(provider_payload)
    ok, error = safe_write_session(session_path, json.dumps(payload, ensure_ascii=False, indent=2))
    if not ok:
        raise RuntimeError(error or f"failed to write session file: {session_path}")
    return session_path


def launch_session_id(agent_name: str) -> str:
    import uuid

    return f"ccb-{agent_name}-{uuid.uuid4().hex[:12]}"


def session_filename(spec) -> str:
    return session_filename_for_agent(spec.provider, spec.name)


def pane_title_marker(context, spec) -> str:
    return build_pane_title_marker(
        project_id=str(getattr(context.project, "project_id", "") or ""),
        agent_name=spec.name,
    )


__all__ = [
    "launch_session_id",
    "pane_title_marker",
    "session_filename",
    "write_session_file",
]
