from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any


class OpenCodeStorageAccessor:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser()
        self._db_path_hint: Path | None = None

    def session_dir(self, project_id: str) -> Path:
        return self.root / "session" / project_id

    def message_dir(self, session_id: str) -> Path:
        nested = self.root / "message" / session_id
        if nested.exists():
            return nested
        return self.root / "message"

    def part_dir(self, message_id: str) -> Path:
        nested = self.root / "part" / message_id
        if nested.exists():
            return nested
        return self.root / "part"

    def load_json(self, path: Path) -> dict:
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def load_json_blob(self, raw: Any) -> dict:
        if isinstance(raw, dict):
            return raw
        if not isinstance(raw, str) or not raw:
            return {}
        try:
            payload = json.loads(raw)
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def opencode_db_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        env = (os.environ.get("OPENCODE_DB_PATH") or "").strip()
        if env:
            candidates.append(Path(env).expanduser())

        candidates.append(self.root.parent / "opencode.db")
        candidates.append(self.root / "opencode.db")

        out: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            out.append(candidate)
        return out

    def resolve_opencode_db_path(self) -> Path | None:
        cached = self._cached_db_path()
        if cached is not None:
            return cached
        resolved = self._existing_db_candidate()
        self._db_path_hint = resolved
        return resolved

    def fetch_opencode_db_rows(self, query: str, params: tuple[object, ...]) -> list[sqlite3.Row]:
        db_path = self.resolve_opencode_db_path()
        if not db_path:
            return []
        conn = _open_readonly_connection(db_path)
        if conn is None:
            return []
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 200")
            return _row_results(conn.execute(query, params).fetchall())
        except Exception:
            return []
        finally:
            _close_connection(conn)

    @staticmethod
    def message_sort_key(message: dict) -> tuple[int, float, str]:
        created = (message.get("time") or {}).get("created")
        try:
            created_i = int(created)
        except Exception:
            created_i = -1
        try:
            mtime = Path(message.get("_path", "")).stat().st_mtime if message.get("_path") else 0.0
        except Exception:
            mtime = 0.0
        message_id = message.get("id") if isinstance(message.get("id"), str) else ""
        return created_i, mtime, message_id

    @staticmethod
    def part_sort_key(part: dict) -> tuple[int, float, str]:
        started = (part.get("time") or {}).get("start")
        try:
            started_i = int(started)
        except Exception:
            started_i = -1
        try:
            mtime = Path(part.get("_path", "")).stat().st_mtime if part.get("_path") else 0.0
        except Exception:
            mtime = 0.0
        part_id = part.get("id") if isinstance(part.get("id"), str) else ""
        return started_i, mtime, part_id

    def _cached_db_path(self) -> Path | None:
        candidate = self._db_path_hint
        if candidate is None:
            return None
        try:
            if candidate.exists():
                return candidate
        except Exception:
            return None
        return None

    def _existing_db_candidate(self) -> Path | None:
        for candidate in self.opencode_db_candidates():
            try:
                if candidate.exists() and candidate.is_file():
                    return candidate
            except Exception:
                continue
        return None


def _open_readonly_connection(db_path: Path) -> sqlite3.Connection | None:
    return _connect_via_uri(db_path) or _connect_direct(db_path)


def _connect_via_uri(db_path: Path) -> sqlite3.Connection | None:
    try:
        db_uri = f"{db_path.resolve().as_uri()}?mode=ro"
        return sqlite3.connect(db_uri, uri=True, timeout=0.2)
    except Exception:
        return None


def _connect_direct(db_path: Path) -> sqlite3.Connection | None:
    try:
        return sqlite3.connect(str(db_path), timeout=0.2)
    except Exception:
        return None


def _row_results(rows: list[object]) -> list[sqlite3.Row]:
    return [row for row in rows if isinstance(row, sqlite3.Row)]


def _close_connection(conn: sqlite3.Connection | None) -> None:
    try:
        if conn is not None:
            conn.close()
    except Exception:
        pass
