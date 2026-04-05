from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from ..session import find_project_session_file as find_droid_project_session_file


def find_droid_session_file(cwd: Path) -> Optional[Path]:
    env_session = (os.environ.get("CCB_SESSION_FILE") or "").strip()
    if env_session:
        try:
            session_path = Path(os.path.expanduser(env_session))
            if session_path.name == ".droid-session" and session_path.is_file():
                return session_path
        except Exception:
            pass
    return find_droid_project_session_file(cwd)


def load_droid_session_info(project_session: Optional[Path]) -> Optional[dict]:
    if not project_session:
        return None
    try:
        with project_session.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("active", False) is False:
        return None
    data["_session_file"] = str(project_session)
    return data
