from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Optional

from project_id import compute_ccb_project_id
from provider_sessions.files import safe_write_session


def find_opencode_session_file(
    *,
    cwd: Path | None = None,
    finder: Callable[[Path], Optional[Path]],
) -> Optional[Path]:
    env_session = (os.environ.get("CCB_SESSION_FILE") or "").strip()
    if env_session:
        try:
            session_path = Path(os.path.expanduser(env_session))
            if session_path.name == ".opencode-session" and session_path.is_file():
                return session_path
        except Exception:
            pass
    return finder(cwd or Path.cwd())


def load_opencode_session_info(*, session_finder: Callable[[], Optional[Path]]) -> Optional[dict]:
    if "CCB_SESSION_ID" in os.environ:
        result = {
            "ccb_session_id": os.environ["CCB_SESSION_ID"],
            "runtime_dir": os.environ["OPENCODE_RUNTIME_DIR"],
            "terminal": os.environ.get("OPENCODE_TERMINAL", "tmux"),
            "tmux_session": os.environ.get("OPENCODE_TMUX_SESSION", ""),
            "pane_id": os.environ.get("OPENCODE_TMUX_SESSION", ""),
            "_session_file": None,
        }
        session_file = session_finder()
        if session_file:
            try:
                with session_file.open("r", encoding="utf-8-sig") as handle:
                    file_data = json.load(handle)
                if isinstance(file_data, dict):
                    result["opencode_session_path"] = file_data.get("opencode_session_path")
                    result["_session_file"] = str(session_file)
                    if not result.get("pane_title_marker"):
                        result["pane_title_marker"] = file_data.get("pane_title_marker", "")
                    if not result.get("opencode_session_id"):
                        result["opencode_session_id"] = file_data.get("opencode_session_id")
                    if not result.get("opencode_project_id"):
                        result["opencode_project_id"] = file_data.get("opencode_project_id")
            except Exception:
                pass
        return result

    project_session = session_finder()
    if not project_session:
        return None

    try:
        with project_session.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except Exception:
        return None

    if not isinstance(data, dict) or not data.get("active", False):
        return None

    runtime_dir = Path(data.get("runtime_dir", ""))
    if not runtime_dir.exists():
        return None

    data["_session_file"] = str(project_session)
    _ensure_ccb_project_id(data, session_file=project_session)
    return data


def publish_opencode_registry(
    *,
    ccb_session_id: str,
    session_info: dict,
    terminal: str,
    pane_id: str | None,
    project_session_file: str | None,
    upsert_registry_fn,
) -> None:
    try:
        wd = session_info.get("work_dir")
        ccb_pid = compute_ccb_project_id(Path(wd)) if isinstance(wd, str) and wd else ""
        upsert_registry_fn(
            {
                "ccb_session_id": ccb_session_id,
                "ccb_project_id": ccb_pid or None,
                "work_dir": wd,
                "terminal": terminal,
                "providers": {
                    "opencode": {
                        "pane_id": pane_id or None,
                        "pane_title_marker": session_info.get("pane_title_marker"),
                        "session_file": project_session_file,
                        "opencode_project_id": session_info.get("opencode_project_id"),
                        "opencode_session_id": session_info.get("opencode_session_id"),
                    }
                },
            }
        )
    except Exception:
        pass


def _ensure_ccb_project_id(data: dict, *, session_file: Path) -> None:
    try:
        if (data.get("ccb_project_id") or "").strip():
            return
        wd = data.get("work_dir")
        if isinstance(wd, str) and wd.strip():
            data["ccb_project_id"] = compute_ccb_project_id(Path(wd.strip()))
            safe_write_session(session_file, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    except Exception:
        pass
