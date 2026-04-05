from __future__ import annotations

import json
from pathlib import Path

from launcher.session.payloads import build_target_session_data
from launcher.session.target_registry import upsert_provider_registry
from launcher.session.target_write_runtime.common import ensure_session_writable, write_payload


def write_simple_target_session(
    store,
    provider: str,
    runtime: Path,
    tmux_session: str | None,
    *,
    pane_id: str | None = None,
    pane_title_marker: str | None = None,
    start_cmd: str | None = None,
    extra_data: dict | None = None,
    extra_registry: dict | None = None,
) -> bool:
    session_file = store.project_session_path_fn(f".{provider}-session")
    if not ensure_session_writable(store, session_file):
        return False

    data = build_target_session_data(
        provider=provider,
        ccb_session_id=store.ccb_session_id,
        project_root=store.project_root,
        invocation_dir=store.invocation_dir,
        terminal_type=store.terminal_type,
        runtime=runtime,
        tmux_session=tmux_session,
        pane_id=pane_id,
        pane_title_marker=pane_title_marker,
        start_cmd=start_cmd,
        compute_project_id_fn=store.compute_project_id_fn,
        normalize_path_for_match_fn=store.normalize_path_for_match_fn,
        extra_data=extra_data,
    )

    if not write_payload(store, session_file, json.dumps(data, ensure_ascii=False, indent=2)):
        return False
    upsert_provider_registry(
        store,
        provider,
        pane_id=pane_id,
        pane_title_marker=pane_title_marker,
        session_file=session_file,
        extra_registry=extra_registry,
    )
    return True
