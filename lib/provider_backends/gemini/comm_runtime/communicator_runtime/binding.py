from __future__ import annotations

from pathlib import Path


def publish_initial_registry_binding(comm, *, publish_registry_binding_fn) -> None:
    try:
        wd = comm.session_info.get("work_dir")
        publish_registry_binding_fn(
            ccb_session_id=comm.ccb_session_id,
            ccb_project_id=str(comm.session_info.get("ccb_project_id") or "").strip(),
            work_dir=wd,
            terminal=comm.terminal,
            pane_id=comm.pane_id or None,
            pane_title_marker=comm.session_info.get("pane_title_marker"),
            session_file=comm.project_session_file,
            gemini_session_id=str(comm.session_info.get("gemini_session_id") or "").strip(),
            gemini_session_path=str(
                comm.session_info.get("gemini_session_path") or comm.session_info.get("session_path") or ""
            ).strip(),
        )
    except Exception:
        pass


def remember_gemini_session(
    comm,
    session_path: Path,
    *,
    update_project_session_binding_fn,
    publish_registry_binding_fn,
) -> None:
    if not session_path or not comm.project_session_file:
        return
    binding = update_project_session_binding_fn(project_file=Path(comm.project_session_file), session_path=session_path)
    if binding is None:
        return

    publish_registry_binding_fn(
        ccb_session_id=comm.ccb_session_id,
        ccb_project_id=binding.ccb_project_id,
        work_dir=comm.session_info.get("work_dir"),
        terminal=comm.terminal,
        pane_id=comm.pane_id or None,
        pane_title_marker=comm.session_info.get("pane_title_marker"),
        session_file=str(comm.project_session_file),
        gemini_session_id=binding.session_id,
        gemini_session_path=binding.session_path,
    )

    comm.session_info["gemini_session_path"] = binding.session_path
    if binding.session_id:
        comm.session_info["gemini_session_id"] = binding.session_id


__all__ = [
    "publish_initial_registry_binding",
    "remember_gemini_session",
]
