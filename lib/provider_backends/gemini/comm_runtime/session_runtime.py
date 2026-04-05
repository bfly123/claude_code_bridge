from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Optional

from .project_hash import read_gemini_session_id


def find_gemini_session_file(
    *,
    cwd: Path | None = None,
    finder: Callable[[Path], Optional[Path]],
) -> Optional[Path]:
    env_session = (os.environ.get("CCB_SESSION_FILE") or "").strip()
    if env_session:
        try:
            session_path = Path(os.path.expanduser(env_session))
            if session_path.name == ".gemini-session" and session_path.is_file():
                return session_path
        except Exception:
            pass
    return finder(cwd or Path.cwd())


def load_gemini_session_info(*, session_finder: Callable[[], Optional[Path]]):
    if "CCB_SESSION_ID" in os.environ:
        result = {
            "ccb_session_id": os.environ["CCB_SESSION_ID"],
            "runtime_dir": os.environ["GEMINI_RUNTIME_DIR"],
            "terminal": os.environ.get("GEMINI_TERMINAL", "tmux"),
            "tmux_session": os.environ.get("GEMINI_TMUX_SESSION", ""),
            "pane_id": os.environ.get("GEMINI_TMUX_SESSION", ""),
            "_session_file": None,
        }
        session_file = session_finder()
        if session_file:
            try:
                with open(session_file, "r", encoding="utf-8") as handle:
                    file_data = json.load(handle)
                if isinstance(file_data, dict):
                    result["gemini_session_path"] = file_data.get("gemini_session_path")
                    result["_session_file"] = str(session_file)
                    if not result["pane_id"]:
                        result["pane_id"] = file_data.get("pane_id", "")
                    if not result["tmux_session"]:
                        result["tmux_session"] = file_data.get("tmux_session", "")
                    if not result.get("pane_title_marker"):
                        result["pane_title_marker"] = file_data.get("pane_title_marker", "")
                    if not result.get("gemini_session_id"):
                        result["gemini_session_id"] = file_data.get("gemini_session_id") or read_gemini_session_id(Path(str(file_data.get("gemini_session_path") or "")))
            except Exception:
                pass
        return result

    project_session = session_finder()
    if not project_session:
        return None
    try:
        with open(project_session, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return None
    if not isinstance(data, dict) or not data.get("active", False):
        return None
    runtime_dir = Path(data.get("runtime_dir", ""))
    if not runtime_dir.exists():
        return None
    data["_session_file"] = str(project_session)
    return data
