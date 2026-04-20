from __future__ import annotations

import json
import time
from pathlib import Path

from provider_core.pathing import find_session_file_for_work_dir, session_filename_for_instance
from provider_sessions.files import safe_write_session


def find_project_session_file(work_dir: Path, instance: str | None = None) -> Path | None:
    filename = session_filename_for_instance(".droid-session", instance)
    return find_session_file_for_work_dir(work_dir, filename)


def read_json(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8-sig")
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def write_back(session) -> None:
    payload = json.dumps(session.data, ensure_ascii=False, indent=2) + "\n"
    safe_write_session(session.session_file, payload)


__all__ = ["find_project_session_file", "now_str", "read_json", "write_back"]
