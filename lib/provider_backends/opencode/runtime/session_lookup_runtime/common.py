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


__all__ = ["coerce_updated", "directories_match", "session_entry"]
