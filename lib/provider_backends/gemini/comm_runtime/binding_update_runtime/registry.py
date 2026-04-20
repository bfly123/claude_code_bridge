from __future__ import annotations

from pane_registry_runtime import upsert_registry


def publish_registry_binding(
    *,
    ccb_session_id: str,
    ccb_project_id: str,
    work_dir: str | None,
    terminal: str,
    pane_id: str | None,
    pane_title_marker: str | None,
    session_file: str | None,
    gemini_session_id: str,
    gemini_session_path: str,
) -> None:
    try:
        upsert_registry(
            {
                "ccb_session_id": ccb_session_id,
                "ccb_project_id": ccb_project_id or None,
                "work_dir": work_dir,
                "terminal": terminal,
                "providers": {
                    "gemini": {
                        "pane_id": pane_id or None,
                        "pane_title_marker": pane_title_marker,
                        "session_file": session_file,
                        "gemini_session_id": gemini_session_id or None,
                        "gemini_session_path": gemini_session_path,
                    }
                },
            }
        )
    except Exception:
        pass


__all__ = ["publish_registry_binding"]
