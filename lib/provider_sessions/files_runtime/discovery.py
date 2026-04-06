from __future__ import annotations

from pathlib import Path

from project.discovery import find_nearest_project_anchor, find_workspace_binding, load_workspace_binding, project_ccb_dir


def find_project_session_file(work_dir: Path, session_filename: str) -> Path | None:
    try:
        current = Path(work_dir).resolve()
    except Exception:
        current = Path(work_dir).absolute()

    binding_candidate = _session_file_from_workspace_binding(current, session_filename)
    if binding_candidate is not None:
        return binding_candidate

    anchor = find_nearest_project_anchor(current)
    if anchor is None:
        return None
    candidate = project_ccb_dir(anchor) / session_filename
    return candidate if candidate.exists() else None


def _session_file_from_workspace_binding(current: Path, session_filename: str) -> Path | None:
    binding_path = find_workspace_binding(current)
    if binding_path is None:
        return None
    binding = load_workspace_binding(binding_path)
    target_project = Path(str(binding['target_project'])).expanduser()
    try:
        target_project = target_project.resolve()
    except Exception:
        target_project = target_project.absolute()
    candidate = project_ccb_dir(target_project) / session_filename
    return candidate if candidate.exists() else None


__all__ = ['find_project_session_file']
