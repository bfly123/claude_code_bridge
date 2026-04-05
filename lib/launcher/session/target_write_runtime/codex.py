from __future__ import annotations

import json
import time
from pathlib import Path

from launcher.session.target_registry import upsert_provider_registry
from launcher.session.target_write_runtime.common import ensure_session_writable, write_payload


def write_codex_session(
    store,
    runtime: Path,
    tmux_session: str | None,
    input_fifo: Path,
    output_fifo: Path,
    *,
    pane_id: str | None = None,
    pane_title_marker: str | None = None,
    codex_start_cmd: str | None = None,
    resume: bool = False,
) -> bool:
    session_file = store.project_session_path_fn(".codex-session")
    if not ensure_session_writable(store, session_file):
        return False

    data = store.read_session_json_fn(session_file) if session_file.exists() else {}
    if not resume:
        data = store.clear_codex_log_binding_fn(data)

    work_dir = store.project_root
    data.update(
        {
            "ccb_session_id": store.ccb_session_id,
            "ccb_project_id": store.compute_project_id_fn(work_dir),
            "runtime_dir": str(runtime),
            "input_fifo": str(input_fifo),
            "output_fifo": str(output_fifo),
            "terminal": store.terminal_type,
            "tmux_session": tmux_session,
            "pane_id": pane_id,
            "pane_title_marker": pane_title_marker,
            "tmux_log": str(runtime / "bridge_output.log"),
            "work_dir": str(work_dir),
            "work_dir_norm": store.normalize_path_for_match_fn(str(work_dir)),
            "start_dir": str(store.invocation_dir),
            "active": True,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    if codex_start_cmd:
        data["codex_start_cmd"] = str(codex_start_cmd)
        data["start_cmd"] = str(codex_start_cmd)

    if not write_payload(store, session_file, json.dumps(data, ensure_ascii=False, indent=2)):
        return False
    upsert_provider_registry(
        store,
        "codex",
        pane_id=pane_id,
        pane_title_marker=pane_title_marker,
        session_file=session_file,
    )
    return True
