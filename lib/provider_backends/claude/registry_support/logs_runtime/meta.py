from __future__ import annotations

import json
from pathlib import Path


def read_session_meta(log_path: Path) -> tuple[str | None, str | None, bool | None]:
    try:
        with log_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for _ in range(30):
                line = handle.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if not isinstance(entry, dict):
                    continue
                cwd = entry.get("cwd") or entry.get("projectPath")
                sid = entry.get("sessionId") or entry.get("id")
                is_sidechain = entry.get("isSidechain")
                cwd_str = str(cwd).strip() if isinstance(cwd, str) else None
                sid_str = str(sid).strip() if isinstance(sid, str) else None
                sidechain_bool: bool | None = None
                if is_sidechain is True:
                    sidechain_bool = True
                elif is_sidechain is False:
                    sidechain_bool = False
                if cwd_str or sid_str:
                    return cwd_str or None, sid_str or None, sidechain_bool
    except OSError:
        return None, None, None
    return None, None, None


__all__ = ["read_session_meta"]
