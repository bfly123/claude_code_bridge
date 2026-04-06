from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from provider_core.session_binding_runtime import find_bound_session_file


def find_droid_session_file(cwd: Path) -> Optional[Path]:
    return find_bound_session_file(
        provider="droid",
        base_filename=".droid-session",
        work_dir=cwd,
    )


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
