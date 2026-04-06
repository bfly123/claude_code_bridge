from __future__ import annotations

from .constants import REMOTE_MAIN_COMMIT_API
from .transport import fetch_json_via_curl, fetch_json_via_urllib


def get_remote_version_info() -> dict | None:
    data = None
    try:
        data = fetch_json_via_urllib(REMOTE_MAIN_COMMIT_API, timeout=5)
    except Exception:
        data = None
    if data is None:
        data = fetch_json_via_curl(REMOTE_MAIN_COMMIT_API, timeout=10)
    if not isinstance(data, dict):
        return None
    commit = str(data.get("sha", "") or "")[:7]
    date_str = str(data.get("commit", {}).get("committer", {}).get("date", "") or "")
    date = date_str[:10] if date_str else None
    return {"commit": commit, "date": date}


__all__ = ['get_remote_version_info']
