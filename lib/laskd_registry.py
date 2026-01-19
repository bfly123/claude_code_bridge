"""
Session registry for laskd - manages Claude session bindings with background refresh.

Monitors active sessions and refreshes log bindings periodically to adapt to session switches.
"""

from __future__ import annotations

import heapq
import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from laskd_session import ClaudeProjectSession, load_project_session
from session_utils import find_project_session_file


CLAUDE_PROJECTS_ROOT = Path(
    os.environ.get("CLAUDE_PROJECTS_ROOT")
    or os.environ.get("CLAUDE_PROJECT_ROOT")
    or (Path.home() / ".claude" / "projects")
).expanduser()

SESSION_ID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, str(default)) or str(default))
    except Exception:
        return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)) or str(default))
    except Exception:
        return default


def _project_key_for_path(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def _normalize_project_path(value: str | Path) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        path = Path(raw).expanduser()
        try:
            path = path.resolve()
        except Exception:
            path = path.absolute()
        raw = str(path)
    except Exception:
        raw = str(value)
    raw = raw.replace("\\", "/").rstrip("/")
    if os.name == "nt":
        raw = raw.lower()
    return raw


def _candidate_project_paths(work_dir: Path) -> list[str]:
    candidates: list[Path] = []
    env_pwd = os.environ.get("PWD")
    if env_pwd:
        try:
            candidates.append(Path(env_pwd))
        except Exception:
            pass
    candidates.append(work_dir)
    try:
        candidates.append(work_dir.resolve())
    except Exception:
        pass
    out: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_project_path(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _extract_session_id_from_start_cmd(start_cmd: str) -> Optional[str]:
    if not start_cmd:
        return None
    match = SESSION_ID_PATTERN.search(start_cmd)
    if not match:
        return None
    return match.group(0)


def _find_log_for_session_id(session_id: str, *, root: Path = CLAUDE_PROJECTS_ROOT) -> Optional[Path]:
    root = Path(root).expanduser()
    if not session_id or not root.exists():
        return None
    latest: Optional[Path] = None
    latest_mtime = -1.0
    try:
        patterns = [f"**/{session_id}.jsonl", f"**/*{session_id}*.jsonl"]
        seen: set[str] = set()
        for pattern in patterns:
            for p in root.glob(pattern):
                if not p.is_file():
                    continue
                path_str = str(p)
                if path_str in seen:
                    continue
                seen.add(path_str)
                try:
                    mtime = p.stat().st_mtime
                except OSError:
                    continue
                if mtime >= latest_mtime:
                    latest = p
                    latest_mtime = mtime
    except Exception:
        return None
    return latest


def _read_session_meta(log_path: Path) -> tuple[Optional[str], Optional[str], Optional[bool]]:
    """
    Read session metadata for (cwd, session_id, is_sidechain).
    Claude logs have various structures; we scan the first 30 lines.
    """
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
                sidechain_bool: Optional[bool] = None
                if is_sidechain is True:
                    sidechain_bool = True
                elif is_sidechain is False:
                    sidechain_bool = False
                if cwd_str or sid_str:
                    return cwd_str or None, sid_str or None, sidechain_bool
    except OSError:
        return None, None, None
    return None, None, None


def _path_within(child: str, parent: str) -> bool:
    """Check if child path is within parent path (case-insensitive on Windows)."""
    try:
        child_path = Path(child).expanduser()
        parent_path = Path(parent).expanduser()
        try:
            child_path = child_path.resolve()
        except Exception:
            child_path = child_path.absolute()
        try:
            parent_path = parent_path.resolve()
        except Exception:
            parent_path = parent_path.absolute()
        child = str(child_path)
        parent = str(parent_path)
    except Exception:
        pass
    if os.name == "nt":
        child = child.lower().replace("\\", "/")
        parent = parent.lower().replace("\\", "/")
    else:
        child = child.replace("\\", "/")
        parent = parent.replace("\\", "/")
    child = child.rstrip("/")
    parent = parent.rstrip("/")
    if child == parent:
        return True
    return child.startswith(parent + "/")


def _scan_latest_log_for_work_dir(
    work_dir: Path, *, root: Path = CLAUDE_PROJECTS_ROOT, scan_limit: int
) -> tuple[Optional[Path], Optional[str]]:
    """
    Scan Claude projects and find the latest log whose cwd/projectPath is within work_dir.
    Uses a bounded heap so we only inspect the N most recently modified logs.
    """
    root = Path(root).expanduser()
    if not root.exists():
        return None, None

    work_dir_str = str(work_dir)

    heap: list[tuple[float, str]] = []
    try:
        for p in root.glob("**/*.jsonl"):
            if not p.is_file() or p.name.startswith("."):
                continue
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            item = (mtime, str(p))
            if len(heap) < scan_limit:
                heapq.heappush(heap, item)
            else:
                if item[0] > heap[0][0]:
                    heapq.heapreplace(heap, item)
    except Exception:
        return None, None

    candidates = sorted(heap, key=lambda x: x[0], reverse=True)
    for _, path_str in candidates:
        path = Path(path_str)
        cwd, sid, is_sidechain = _read_session_meta(path)
        if is_sidechain is True:
            continue
        if not cwd:
            continue
        if _path_within(cwd, work_dir_str):
            return path, sid
    return None, None


def _parse_sessions_index(work_dir: Path, *, root: Path = CLAUDE_PROJECTS_ROOT) -> Optional[Path]:
    """
    Parse sessions-index.json to find the correct session for work_dir.
    Returns the log path if found.
    """
    candidates = set(_candidate_project_paths(work_dir))

    project_key = _project_key_for_path(work_dir)
    project_dir = root / project_key
    index_path = project_dir / "sessions-index.json"
    if not index_path.exists():
        try:
            resolved = work_dir.resolve()
        except Exception:
            resolved = work_dir
        if resolved != work_dir:
            alt_key = _project_key_for_path(resolved)
            index_path = root / alt_key / "sessions-index.json"
            project_dir = root / alt_key
    if not index_path.exists():
        return None

    try:
        payload = json.loads(index_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None

    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return None

    best_path: Optional[Path] = None
    best_mtime = -1
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("isSidechain") is True:
            continue
        project_path = entry.get("projectPath")
        if isinstance(project_path, str) and project_path.strip():
            normalized = _normalize_project_path(project_path)
            if candidates and normalized and normalized not in candidates:
                continue
        elif candidates:
            continue
        full_path = entry.get("fullPath")
        if not isinstance(full_path, str) or not full_path.strip():
            continue
        try:
            session_path = Path(full_path).expanduser()
        except Exception:
            continue
        if not session_path.is_absolute():
            session_path = (project_dir / session_path).expanduser()
        if not session_path.exists():
            continue
        mtime_raw = entry.get("fileMtime")
        mtime = None
        if isinstance(mtime_raw, (int, float)):
            mtime = int(mtime_raw)
        elif isinstance(mtime_raw, str) and mtime_raw.strip().isdigit():
            try:
                mtime = int(mtime_raw.strip())
            except Exception:
                mtime = None
        if mtime is None:
            try:
                mtime = int(session_path.stat().st_mtime * 1000)
            except OSError:
                mtime = None
        if mtime is None:
            continue
        if mtime > best_mtime:
            best_mtime = mtime
            best_path = session_path
    return best_path


def _should_overwrite_binding(current: Optional[Path], candidate: Path) -> bool:
    if not current:
        return True
    if not current.exists():
        return True
    try:
        return candidate.stat().st_mtime > current.stat().st_mtime
    except OSError:
        return True


def _refresh_claude_log_binding(
    session: ClaudeProjectSession,
    *,
    root: Path = CLAUDE_PROJECTS_ROOT,
    scan_limit: int,
    force_scan: bool,
) -> bool:
    """
    Refresh .claude-session claude_session_id/claude_session_path.

    Priority:
      1) Parse session_id from start_cmd (e.g., "claude resume <uuid>") and bind to its log.
      2) Use sessions-index.json to select the best session.
      3) Fallback scan latest log by work_dir (only when forced or when (1)/(2) fail).
    """
    current_log_str = session.claude_session_path
    current_log = Path(current_log_str).expanduser() if current_log_str else None

    start_cmd = str(session.data.get("claude_start_cmd") or session.data.get("start_cmd") or "").strip()
    intended_sid = _extract_session_id_from_start_cmd(start_cmd)
    intended_log: Optional[Path] = None
    if intended_sid:
        intended_log = _find_log_for_session_id(intended_sid, root=root)
        if intended_log and intended_log.exists():
            if _should_overwrite_binding(current_log, intended_log) or session.claude_session_id != intended_sid:
                session.update_claude_binding(session_path=intended_log, session_id=intended_sid)
                return True
            return False

    index_session = _parse_sessions_index(Path(session.work_dir), root=root)
    if index_session and index_session.exists():
        index_sid = index_session.stem
        if _should_overwrite_binding(current_log, index_session) or session.claude_session_id != index_sid:
            session.update_claude_binding(session_path=index_session, session_id=index_sid)
            return True
        if not force_scan:
            return False

    need_scan = bool(force_scan or (not intended_log and not index_session))
    if not need_scan:
        return False

    candidate_log, candidate_sid = _scan_latest_log_for_work_dir(
        Path(session.work_dir), root=root, scan_limit=scan_limit
    )
    if not candidate_log or not candidate_log.exists():
        return False

    if _should_overwrite_binding(current_log, candidate_log) or (
        candidate_sid and candidate_sid != session.claude_session_id
    ):
        session.update_claude_binding(session_path=candidate_log, session_id=candidate_sid)
        return True
    return False


def _write_log(line: str) -> None:
    try:
        from askd_runtime import log_path, write_log
        from providers import LASKD_SPEC
        write_log(log_path(LASKD_SPEC.log_file_name), line)
    except Exception:
        pass


@dataclass
class _SessionEntry:
    work_dir: Path
    session: Optional[ClaudeProjectSession]
    session_file: Optional[Path] = None
    file_mtime: float = 0.0
    last_check: float = 0.0
    valid: bool = False
    next_bind_refresh: float = 0.0
    bind_backoff_s: float = 0.0


class LaskdSessionRegistry:
    """Manages and monitors all active Claude sessions."""

    CHECK_INTERVAL = 10.0  # seconds between validity checks

    def __init__(self, *, claude_root: Path = CLAUDE_PROJECTS_ROOT):
        self._lock = threading.Lock()
        self._sessions: dict[str, _SessionEntry] = {}  # work_dir -> entry
        self._stop = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._claude_root = claude_root

    def start_monitor(self) -> None:
        if self._monitor_thread is None:
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()

    def stop_monitor(self) -> None:
        self._stop.set()

    def get_session(self, work_dir: Path) -> Optional[ClaudeProjectSession]:
        key = str(work_dir)
        with self._lock:
            entry = self._sessions.get(key)
            if entry:
                session_file = entry.session_file or find_project_session_file(work_dir) or (work_dir / ".ccb_config" / ".claude-session")
                if session_file.exists():
                    try:
                        current_mtime = session_file.stat().st_mtime
                        if (not entry.session_file) or (session_file != entry.session_file) or (current_mtime != entry.file_mtime):
                            _write_log(f"[INFO] Session file changed, reloading: {work_dir}")
                            entry = self._load_and_cache(work_dir)
                    except Exception:
                        pass

                if entry and entry.valid:
                    return entry.session
            else:
                entry = self._load_and_cache(work_dir)
                if entry:
                    return entry.session

        return None

    def register_session(self, work_dir: Path, session: ClaudeProjectSession) -> None:
        """Register an active session for monitoring."""
        key = str(work_dir)
        session_file = session.session_file
        mtime = 0.0
        if session_file and session_file.exists():
            try:
                mtime = session_file.stat().st_mtime
            except Exception:
                pass

        with self._lock:
            entry = _SessionEntry(
                work_dir=work_dir,
                session=session,
                session_file=session_file,
                file_mtime=mtime,
                last_check=time.time(),
                valid=True,
                next_bind_refresh=0.0,
                bind_backoff_s=0.0,
            )
            self._sessions[key] = entry

    def _load_and_cache(self, work_dir: Path) -> Optional[_SessionEntry]:
        session = load_project_session(work_dir)
        session_file = session.session_file if session else (find_project_session_file(work_dir) or (work_dir / ".ccb_config" / ".claude-session"))
        mtime = 0.0
        if session_file.exists():
            try:
                mtime = session_file.stat().st_mtime
            except Exception:
                pass

        valid = False
        if session is not None:
            try:
                ok, _ = session.ensure_pane()
                valid = bool(ok)
            except Exception:
                valid = False

        entry = _SessionEntry(
            work_dir=work_dir,
            session=session,
            session_file=session_file if session_file.exists() else None,
            file_mtime=mtime,
            last_check=time.time(),
            valid=valid,
            next_bind_refresh=0.0,
            bind_backoff_s=0.0,
        )
        self._sessions[str(work_dir)] = entry
        return entry if entry.valid else None

    def invalidate(self, work_dir: Path) -> None:
        key = str(work_dir)
        with self._lock:
            if key in self._sessions:
                self._sessions[key].valid = False
                _write_log(f"[INFO] Session invalidated: {work_dir}")

    def remove(self, work_dir: Path) -> None:
        key = str(work_dir)
        with self._lock:
            if key in self._sessions:
                del self._sessions[key]
                _write_log(f"[INFO] Session removed: {work_dir}")

    def _monitor_loop(self) -> None:
        while not self._stop.wait(self.CHECK_INTERVAL):
            self._check_all_sessions()

    def _check_all_sessions(self) -> None:
        now = time.time()
        refresh_interval_s = _env_float("CCB_LASKD_BIND_REFRESH_INTERVAL", 60.0)
        scan_limit = max(50, min(20000, _env_int("CCB_LASKD_BIND_SCAN_LIMIT", 400)))

        with self._lock:
            snapshot = [(key, entry.work_dir) for key, entry in self._sessions.items() if entry.valid]

        for key, work_dir in snapshot:
            try:
                self._check_one(key, work_dir, now=now, refresh_interval_s=refresh_interval_s, scan_limit=scan_limit)
            except Exception:
                continue

        with self._lock:
            keys_to_remove: list[str] = []
            for key, entry in list(self._sessions.items()):
                if not entry.valid and now - entry.last_check > 300:
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._sessions[key]

    def _check_one(self, key: str, work_dir: Path, *, now: float, refresh_interval_s: float, scan_limit: int) -> None:
        session_file = find_project_session_file(work_dir) or (work_dir / ".ccb_config" / ".claude-session")
        try:
            exists = session_file.exists()
        except Exception:
            exists = False

        if not exists:
            with self._lock:
                entry = self._sessions.get(key)
                if entry and entry.valid:
                    _write_log(f"[WARN] Session file deleted: {work_dir}")
                    entry.valid = False
                    entry.last_check = now
            return

        try:
            current_mtime = session_file.stat().st_mtime
        except Exception:
            current_mtime = 0.0

        session: Optional[ClaudeProjectSession] = None
        file_changed = False

        with self._lock:
            entry = self._sessions.get(key)
            if not entry or not entry.valid:
                return
            file_changed = bool((entry.session_file != session_file) or (entry.file_mtime != current_mtime))
            if file_changed or (entry.session is None):
                session = load_project_session(work_dir)
                entry.session = session
                entry.session_file = session_file
                entry.file_mtime = current_mtime
            else:
                session = entry.session

        if not session:
            with self._lock:
                entry2 = self._sessions.get(key)
                if entry2 and entry2.valid:
                    entry2.valid = False
                    entry2.last_check = now
            return

        try:
            ok, _ = session.ensure_pane()
        except Exception:
            ok = False
        if not ok:
            with self._lock:
                entry2 = self._sessions.get(key)
                if entry2 and entry2.valid:
                    _write_log(f"[WARN] Session pane invalid: {work_dir}")
                    entry2.valid = False
                    entry2.last_check = now
            return

        with self._lock:
            entry3 = self._sessions.get(key)
            if not entry3 or not entry3.valid:
                return
            due = now >= (entry3.next_bind_refresh or 0.0)
            if not due and not file_changed:
                entry3.last_check = now
                return
            backoff = entry3.bind_backoff_s or refresh_interval_s

        force_scan = bool(file_changed)
        updated = False
        try:
            updated = _refresh_claude_log_binding(
                session,
                root=self._claude_root,
                scan_limit=scan_limit,
                force_scan=force_scan,
            )
        except Exception:
            updated = False

        with self._lock:
            entry4 = self._sessions.get(key)
            if not entry4 or not entry4.valid:
                return
            if updated:
                entry4.bind_backoff_s = refresh_interval_s
            else:
                entry4.bind_backoff_s = min(600.0, max(refresh_interval_s, backoff * 2.0))
            entry4.next_bind_refresh = now + entry4.bind_backoff_s
            try:
                entry4.file_mtime = session_file.stat().st_mtime
            except Exception:
                pass
            entry4.last_check = now

    def get_status(self) -> dict:
        with self._lock:
            return {
                "total": len(self._sessions),
                "valid": sum(1 for e in self._sessions.values() if e.valid),
                "sessions": [{"work_dir": str(e.work_dir), "valid": e.valid} for e in self._sessions.values()],
            }


_session_registry: Optional[LaskdSessionRegistry] = None


def get_session_registry() -> LaskdSessionRegistry:
    global _session_registry
    if _session_registry is None:
        _session_registry = LaskdSessionRegistry()
        _session_registry.start_monitor()
    return _session_registry
