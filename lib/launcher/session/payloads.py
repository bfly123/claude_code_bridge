from __future__ import annotations

from pathlib import Path
import time


def build_claude_registry_payload(
    *,
    ccb_session_id: str,
    project_id: str | None,
    project_root: Path,
    terminal: str | None,
    path: Path,
    pane_id: str,
    pane_title_marker: str | None,
    data: dict,
) -> dict:
    return {
        "ccb_session_id": ccb_session_id,
        "ccb_project_id": project_id,
        "work_dir": str(project_root),
        "terminal": terminal,
        "providers": {
            "claude": {
                "pane_id": pane_id,
                "pane_title_marker": pane_title_marker,
                "session_file": str(path),
                "claude_session_id": data.get("claude_session_id"),
                "claude_session_path": data.get("claude_session_path"),
            }
        },
    }


def build_target_session_data(
    *,
    provider: str,
    ccb_session_id: str,
    project_root: Path,
    invocation_dir: Path,
    terminal_type: str | None,
    runtime: Path,
    tmux_session: str | None,
    pane_id: str | None,
    pane_title_marker: str | None,
    start_cmd: str | None,
    compute_project_id_fn,
    normalize_path_for_match_fn,
    extra_data: dict | None = None,
) -> dict:
    data = {
        "ccb_session_id": ccb_session_id,
        "ccb_project_id": compute_project_id_fn(project_root),
        "runtime_dir": str(runtime),
        "terminal": terminal_type,
        "tmux_session": tmux_session,
        "pane_id": pane_id,
        "pane_title_marker": pane_title_marker,
        "work_dir": str(project_root),
        "work_dir_norm": normalize_path_for_match_fn(str(project_root)),
        "start_dir": str(invocation_dir),
        "active": True,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "start_cmd": str(start_cmd) if start_cmd else None,
    }
    if extra_data:
        data.update(extra_data)
    return data


def build_provider_registry_payload(
    *,
    provider: str,
    ccb_session_id: str,
    project_root: Path,
    terminal_type: str | None,
    session_file: Path,
    compute_project_id_fn,
    pane_id: str | None,
    pane_title_marker: str | None,
    extra_registry: dict | None = None,
) -> dict:
    payload = {
        "ccb_session_id": ccb_session_id,
        "ccb_project_id": compute_project_id_fn(project_root),
        "work_dir": str(project_root),
        "terminal": terminal_type,
        "providers": {
            provider: {
                "pane_id": pane_id,
                "pane_title_marker": pane_title_marker,
                "session_file": str(session_file),
            }
        },
    }
    if extra_registry:
        payload["providers"][provider].update(extra_registry)
    return payload


def build_cend_registry_payload(
    *,
    ccb_session_id: str,
    project_root: Path,
    terminal_type: str | None,
    compute_project_id_fn,
    claude_pane_id: str,
    codex_pane_id: str | None,
) -> dict:
    return {
        "ccb_session_id": ccb_session_id,
        "ccb_project_id": compute_project_id_fn(project_root),
        "work_dir": str(Path.cwd()),
        "terminal": terminal_type,
        "providers": {
            "claude": {"pane_id": claude_pane_id},
            "codex": {"pane_id": codex_pane_id},
        },
    }
