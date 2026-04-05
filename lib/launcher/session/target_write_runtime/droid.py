from __future__ import annotations

from pathlib import Path

from launcher.session.droid import read_droid_session_metadata
from launcher.session.target_write_runtime.simple import write_simple_target_session


def write_droid_session(
    store,
    runtime: Path,
    tmux_session: str | None,
    *,
    pane_id: str | None = None,
    pane_title_marker: str | None = None,
    start_cmd: str | None = None,
) -> bool:
    droid_session_id, droid_session_path = read_droid_session_metadata(store.project_root)
    return write_simple_target_session(
        store,
        "droid",
        runtime,
        tmux_session,
        pane_id=pane_id,
        pane_title_marker=pane_title_marker,
        start_cmd=start_cmd,
        extra_data={
            "droid_session_id": droid_session_id,
            "droid_session_path": droid_session_path,
        },
        extra_registry={
            "droid_session_id": droid_session_id,
            "droid_session_path": droid_session_path,
        },
    )
