from __future__ import annotations

from pathlib import Path


def find_log_for_session_id(session_id: str, *, root: Path) -> Path | None:
    root = Path(root).expanduser()
    if not session_id or not root.exists():
        return None
    latest: Path | None = None
    latest_mtime = -1.0
    try:
        patterns = [f'**/{session_id}.jsonl', f'**/*{session_id}*.jsonl']
        seen: set[str] = set()
        for pattern in patterns:
            for path in root.glob(pattern):
                if not path.is_file():
                    continue
                path_str = str(path)
                if path_str in seen:
                    continue
                seen.add(path_str)
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                if mtime >= latest_mtime:
                    latest = path
                    latest_mtime = mtime
    except Exception:
        return None
    return latest


__all__ = ['find_log_for_session_id']
