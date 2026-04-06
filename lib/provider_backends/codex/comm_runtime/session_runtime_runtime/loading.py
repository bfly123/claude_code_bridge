from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable


def load_codex_session_info(*, session_finder: Callable[[], Path | None]):
    env_info = _load_env_session_info(session_finder=session_finder)
    if env_info is not None:
        return env_info
    return _load_project_session_info(session_finder=session_finder)


def _load_env_session_info(*, session_finder: Callable[[], Path | None]):
    if "CCB_SESSION_ID" not in os.environ:
        return None
    result = {
        "ccb_session_id": os.environ["CCB_SESSION_ID"],
        "runtime_dir": os.environ["CODEX_RUNTIME_DIR"],
        "input_fifo": os.environ["CODEX_INPUT_FIFO"],
        "output_fifo": os.environ.get("CODEX_OUTPUT_FIFO", ""),
        "terminal": os.environ.get("CODEX_TERMINAL", "tmux"),
        "tmux_session": os.environ.get("CODEX_TMUX_SESSION", ""),
        "pane_id": os.environ.get("CODEX_TMUX_SESSION", ""),
        "_session_file": None,
    }
    session_file = session_finder()
    return _merge_project_binding(result, session_file=session_file)


def _load_project_session_info(*, session_finder: Callable[[], Path | None]):
    project_session = session_finder()
    if project_session is None:
        return None
    data = _load_session_file(project_session)
    if data is None or not data.get("active", False):
        return None

    runtime_dir = Path(data.get("runtime_dir", ""))
    if not runtime_dir.exists():
        return None

    data["_session_file"] = str(project_session)
    return data


def _merge_project_binding(result: dict[str, object], *, session_file: Path | None):
    if session_file is None:
        return result
    file_data = _load_session_file(session_file)
    if file_data is None:
        return result
    result["codex_session_path"] = file_data.get("codex_session_path")
    result["codex_session_id"] = file_data.get("codex_session_id")
    result["_session_file"] = str(session_file)
    return result


def _load_session_file(session_file: Path) -> dict | None:
    try:
        with open(session_file, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


__all__ = ["load_codex_session_info"]
