from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Optional

from project.identity import compute_ccb_project_id
from provider_core.session_binding_runtime import find_bound_session_file
from provider_sessions.files import safe_write_session


def find_opencode_session_file(
    *,
    cwd: Path | None = None,
    finder: Callable[[Path], Optional[Path]],
) -> Optional[Path]:
    del finder
    return find_bound_session_file(
        provider="opencode",
        base_filename=".opencode-session",
        work_dir=cwd or Path.cwd(),
    )


def load_opencode_session_info(*, session_finder: Callable[[], Optional[Path]]) -> Optional[dict]:
    if "CCB_SESSION_ID" in os.environ:
        result = env_session_info()
        session_file = session_finder()
        if session_file:
            merge_session_file_data(result, session_file)
        return result

    project_session = session_finder()
    if not project_session:
        return None

    data = active_project_session_data(project_session)
    if data is None:
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


def env_session_info() -> dict[str, object]:
    return {
        "ccb_session_id": os.environ["CCB_SESSION_ID"],
        "runtime_dir": os.environ["OPENCODE_RUNTIME_DIR"],
        "terminal": os.environ.get("OPENCODE_TERMINAL", "tmux"),
        "tmux_session": os.environ.get("OPENCODE_TMUX_SESSION", ""),
        "pane_id": os.environ.get("OPENCODE_TMUX_SESSION", ""),
        "_session_file": None,
    }


def merge_session_file_data(result: dict[str, object], session_file: Path) -> None:
    file_data = read_session_json(session_file)
    if file_data is None:
        return
    result["opencode_session_path"] = file_data.get("opencode_session_path")
    result["_session_file"] = str(session_file)
    copy_missing_field(result, file_data, "pane_title_marker", default="")
    copy_missing_field(result, file_data, "opencode_session_id")
    copy_missing_field(result, file_data, "opencode_project_id")


def copy_missing_field(result: dict[str, object], source: dict[str, object], field: str, default: object = None) -> None:
    if result.get(field):
        return
    if field in source:
        result[field] = source.get(field)
        return
    if default is not None:
        result[field] = default


def active_project_session_data(project_session: Path) -> Optional[dict]:
    data = read_session_json(project_session)
    if not isinstance(data, dict) or not data.get("active", False):
        return None
    return data


def read_session_json(session_file: Path) -> Optional[dict]:
    try:
        with session_file.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _ensure_ccb_project_id(data: dict, *, session_file: Path) -> None:
    try:
        if (data.get("ccb_project_id") or "").strip():
            return
        wd = data.get("work_dir")
        if isinstance(wd, str) and wd.strip():
            data["ccb_project_id"] = compute_ccb_project_id(Path(wd.strip()))
            persist_project_session(session_file, data)
    except Exception:
        pass


def persist_project_session(session_file: Path, data: dict) -> None:
    safe_write_session(session_file, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
