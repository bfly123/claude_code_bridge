from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Optional

from provider_core.session_binding_runtime import find_bound_session_file

from .project_hash import read_gemini_session_id


def find_gemini_session_file(
    *,
    cwd: Path | None = None,
    finder: Callable[[Path], Optional[Path]],
) -> Optional[Path]:
    del finder
    return find_bound_session_file(
        provider="gemini",
        base_filename=".gemini-session",
        work_dir=cwd or Path.cwd(),
    )


def load_gemini_session_info(*, session_finder: Callable[[], Optional[Path]]):
    if "CCB_SESSION_ID" in os.environ:
        result = _env_session_result()
        session_file = session_finder()
        if session_file:
            _merge_session_file_data(result, session_file)
        return result

    return _project_session_info(session_finder=session_finder)


def _env_session_result() -> dict[str, object]:
    return {
        "ccb_session_id": os.environ["CCB_SESSION_ID"],
        "runtime_dir": os.environ["GEMINI_RUNTIME_DIR"],
        "terminal": os.environ.get("GEMINI_TERMINAL", "tmux"),
        "tmux_session": os.environ.get("GEMINI_TMUX_SESSION", ""),
        "pane_id": os.environ.get("GEMINI_TMUX_SESSION", ""),
        "_session_file": None,
    }


def _merge_session_file_data(result: dict[str, object], session_file: Path) -> None:
    try:
        with open(session_file, "r", encoding="utf-8") as handle:
            file_data = json.load(handle)
    except Exception:
        return
    if not isinstance(file_data, dict):
        return
    result["gemini_session_path"] = file_data.get("gemini_session_path")
    result["_session_file"] = str(session_file)
    if not result["pane_id"]:
        result["pane_id"] = file_data.get("pane_id", "")
    if not result["tmux_session"]:
        result["tmux_session"] = file_data.get("tmux_session", "")
    if not result.get("pane_title_marker"):
        result["pane_title_marker"] = file_data.get("pane_title_marker", "")
    if not result.get("gemini_session_id"):
        result["gemini_session_id"] = _session_id_from_file_data(file_data)


def _session_id_from_file_data(file_data: dict[str, object]) -> str | None:
    session_id = file_data.get("gemini_session_id")
    if isinstance(session_id, str) and session_id.strip():
        return session_id
    session_path = Path(str(file_data.get("gemini_session_path") or ""))
    return read_gemini_session_id(session_path)


def _project_session_info(*, session_finder: Callable[[], Optional[Path]]):
    project_session = session_finder()
    if not project_session:
        return None
    data = _load_json(project_session)
    if not _active_project_session(data):
        return None
    runtime_dir = Path(data.get("runtime_dir", ""))
    if not runtime_dir.exists():
        return None
    data["_session_file"] = str(project_session)
    return data


def _load_json(path: Path) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _active_project_session(data: dict | None) -> bool:
    return isinstance(data, dict) and bool(data.get("active", False))
