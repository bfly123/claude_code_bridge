from __future__ import annotations

import sys

from pane_registry_runtime import registry_path_for_session, upsert_registry


def publish_registry_binding(
    *,
    ccb_session_id: str,
    ccb_project_id: str,
    work_dir: str | None,
    terminal: str,
    pane_id: str | None,
    pane_title_marker: str | None,
    session_file: str | None,
    codex_session_id: str,
    codex_session_path: str,
) -> None:
    registry_path = registry_path_for_session(ccb_session_id)
    if not registry_path.exists():
        return
    ok = upsert_registry(
        {
            "ccb_session_id": ccb_session_id,
            "ccb_project_id": ccb_project_id or None,
            "work_dir": work_dir,
            "terminal": terminal,
            "providers": {
                "codex": {
                    "pane_id": pane_id or None,
                    "pane_title_marker": pane_title_marker or None,
                    "session_file": session_file,
                    "codex_session_id": codex_session_id or None,
                    "codex_session_path": codex_session_path,
                }
            },
        }
    )
    if not ok:
        print("⚠️  Failed to update Codex registry", file=sys.stderr)


__all__ = ["publish_registry_binding"]
