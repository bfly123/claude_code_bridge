from __future__ import annotations

from opencode_runtime.paths import normalize_path_for_match, path_is_same_or_parent


def directories_match(reader, directory: str) -> bool:
    if not isinstance(directory, str) or not directory:
        return False
    dir_norm = normalize_path_for_match(directory)
    for cwd in reader._work_dir_candidates():
        if reader._allow_parent_match:
            if path_is_same_or_parent(dir_norm, cwd) or path_is_same_or_parent(cwd, dir_norm):
                return True
            continue
        if dir_norm == cwd:
            return True
    return False


def coerce_updated(value) -> int:
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except Exception:
        return -1


def session_entry(*, path, sid: str, directory: str, updated: int) -> dict:
    return {
        "path": path,
        "payload": {
            "id": sid,
            "directory": directory,
            "time": {"updated": updated},
        },
    }


def get_latest_session(reader) -> dict | None:
    session = get_latest_session_from_db(reader)
    if session:
        return session
    return get_latest_session_from_files(reader)


def get_latest_session_from_db(reader) -> dict | None:
    if not reader._work_dir_candidates():
        return None

    rows = reader._fetch_opencode_db_rows("SELECT * FROM session ORDER BY time_updated DESC LIMIT 200", ())
    best_match: dict | None = None
    best_updated = -1
    latest_unfiltered: dict | None = None
    latest_unfiltered_updated = -1

    for row in rows:
        directory = row["directory"]
        if not directories_match(reader, directory):
            continue

        sid = row["id"]
        updated = row["time_updated"]

        if updated > latest_unfiltered_updated:
            latest_unfiltered = session_entry(path=None, sid=sid, directory=directory, updated=updated)
            latest_unfiltered_updated = updated

        if reader._session_id_filter and sid != reader._session_id_filter:
            continue

        if updated > best_updated:
            best_match = session_entry(path=None, sid=sid, directory=directory, updated=updated)
            best_updated = updated

    if (
        reader._session_id_filter
        and reader._allow_session_rollover
        and latest_unfiltered
        and latest_unfiltered_updated > best_updated
    ):
        return latest_unfiltered

    return best_match


def get_latest_session_from_files(reader) -> dict | None:
    sessions_dir = reader._session_dir()
    if not sessions_dir.exists():
        return None

    filtered_match: dict | None = None
    filtered_updated = -1
    if reader._session_id_filter:
        try:
            for path in sessions_dir.glob("ses_*.json"):
                if not path.is_file():
                    continue
                payload = reader._load_json(path)
                sid = payload.get("id")
                if isinstance(sid, str) and sid == reader._session_id_filter:
                    filtered_match = {"path": path, "payload": payload}
                    filtered_updated = coerce_updated((payload.get("time") or {}).get("updated"))
                    break
        except Exception:
            pass

    best_match: dict | None = None
    best_updated = -1
    best_mtime = -1.0
    best_any: dict | None = None
    best_any_updated = -1
    best_any_mtime = -1.0

    try:
        files = [path for path in sessions_dir.glob("ses_*.json") if path.is_file()]
    except Exception:
        files = []

    for path in files:
        payload = reader._load_json(path)
        sid = payload.get("id")
        directory = payload.get("directory")
        updated = coerce_updated((payload.get("time") or {}).get("updated"))
        if not isinstance(sid, str) or not sid:
            continue
        try:
            mtime = path.stat().st_mtime
        except Exception:
            mtime = 0.0

        entry = {"path": path, "payload": payload}
        if updated > best_any_updated or (updated == best_any_updated and mtime >= best_any_mtime):
            best_any = entry
            best_any_updated = updated
            best_any_mtime = mtime

        if not directories_match(reader, directory):
            continue

        if updated > best_updated or (updated == best_updated and mtime >= best_mtime):
            best_match = entry
            best_updated = updated
            best_mtime = mtime

    if filtered_match:
        if best_match and best_updated > filtered_updated:
            return best_match
        return filtered_match

    if best_match:
        return best_match
    if reader._allow_any_session:
        return best_any
    return None


__all__ = [
    "coerce_updated",
    "directories_match",
    "get_latest_session",
    "get_latest_session_from_db",
    "get_latest_session_from_files",
    "session_entry",
]
