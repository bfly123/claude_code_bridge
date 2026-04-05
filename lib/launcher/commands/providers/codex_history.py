from __future__ import annotations

import json
import os
from pathlib import Path
import time

from launcher.session.io import read_session_json, write_session_json


def get_latest_codex_session_id(factory) -> tuple[str | None, bool]:
    project_session = factory.project_session_path_fn(".codex-session")
    root = Path(os.environ.get("CODEX_SESSION_ROOT") or (Path.home() / ".codex" / "sessions")).expanduser()
    if not root.exists():
        return None, False
    root_norm = factory.normalize_path_for_match_fn(str(factory.project_root))
    if not root_norm:
        return None, False
    try:
        logs = sorted(
            (path for path in root.glob("**/*.jsonl") if path.is_file()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except Exception:
        logs = []

    scan_limit = 400
    raw_limit = (os.environ.get("CCB_CODEX_SCAN_LIMIT") or "").strip()
    if raw_limit:
        try:
            scan_limit = max(100, min(20000, int(raw_limit)))
        except Exception:
            scan_limit = 400

    for log_path in logs[:scan_limit]:
        try:
            with log_path.open("r", encoding="utf-8", errors="ignore") as handle:
                head = [handle.readline().strip() for _ in range(30)]
        except OSError:
            continue
        for line in head:
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if not isinstance(entry, dict) or entry.get("type") != "session_meta":
                continue
            payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
            cwd = payload.get("cwd")
            if not isinstance(cwd, str) or not cwd.strip():
                continue
            cwd_norm = factory.normalize_path_for_match_fn(cwd)
            if not factory.normpath_within_fn(cwd_norm, root_norm):
                continue
            session_id = payload.get("id")
            if isinstance(session_id, str) and session_id:
                data = read_session_json(project_session) if project_session.exists() else {}
                data.update(
                    {
                        "codex_session_id": session_id,
                        "codex_session_path": str(log_path),
                        "work_dir": str(factory.project_root),
                        "work_dir_norm": factory.normalize_path_for_match_fn(str(factory.project_root)),
                        "start_dir": str(factory.invocation_dir),
                        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
                write_session_json(project_session, data)
                return session_id, True
    return None, False
