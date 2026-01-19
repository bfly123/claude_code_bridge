from __future__ import annotations

import heapq
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

from worker_pool import BaseSessionWorker, PerSessionWorkerPool

from ccb_protocol import (
    CaskdRequest,
    CaskdResult,
    REQ_ID_PREFIX,

    make_req_id,
    is_done_text,
    strip_done_text,
    wrap_codex_prompt,
)
from caskd_session import CodexProjectSession, compute_session_key, find_project_session_file, load_project_session
from terminal import is_windows
from codex_comm import CodexLogReader, CodexCommunicator, SESSION_ID_PATTERN, SESSION_ROOT
from terminal import get_backend_for_session
from askd_runtime import state_file_path, log_path, write_log, random_token
import askd_rpc
from askd_server import AskDaemonServer
from providers import CASKD_SPEC


def _now_ms() -> int:
    return int(time.time() * 1000)


def _extract_codex_session_id_from_log(log_path: Path) -> Optional[str]:
    try:
        return CodexCommunicator._extract_session_id(log_path)
    except Exception:
        return None


def _tail_state_for_log(log_path: Optional[Path], *, tail_bytes: int) -> dict:
    if not log_path:
        return {"log_path": None, "offset": 0}
    try:
        size = log_path.stat().st_size
    except OSError:
        size = 0
    offset = max(0, int(size) - int(tail_bytes))
    return {"log_path": log_path, "offset": offset}


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _realpath_norm(value: str) -> Optional[str]:
    try:
        return os.path.normcase(os.path.realpath(os.path.expanduser(value or ""))).rstrip("\\/")
    except Exception:
        return None


def _path_within(child: str, parent: str) -> bool:
    child_norm = _realpath_norm(child)
    parent_norm = _realpath_norm(parent)
    if not child_norm or not parent_norm:
        return False
    if child_norm == parent_norm:
        return True
    parent_prefix = parent_norm + os.sep
    return child_norm.startswith(parent_prefix)


def _extract_session_id_from_start_cmd(start_cmd: str) -> Optional[str]:
    if not start_cmd:
        return None
    match = SESSION_ID_PATTERN.search(start_cmd)
    if not match:
        return None
    return match.group(0)


def _find_latest_log_for_session_id(session_id: str, *, session_root: Path = SESSION_ROOT) -> Optional[Path]:
    root = Path(session_root).expanduser()
    if not session_id or not root.exists():
        return None
    latest: Optional[Path] = None
    latest_mtime = -1.0
    try:
        pattern = f"**/*{session_id}*.jsonl"
        for p in root.glob(pattern):
            if not p.is_file():
                continue
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


def _read_session_meta(log_path: Path) -> tuple[Optional[str], Optional[str]]:
    """
    Best-effort read of session_meta for (cwd, session_id).

    Codex logs usually have session_meta on the first line, but we scan a few lines to be robust.
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
                if not isinstance(entry, dict) or entry.get("type") != "session_meta":
                    continue
                payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
                cwd = payload.get("cwd")
                sid = payload.get("id")
                cwd_str = str(cwd).strip() if isinstance(cwd, str) else None
                sid_str = str(sid).strip() if isinstance(sid, str) else None
                return cwd_str or None, sid_str or None
    except OSError:
        return None, None
    return None, None


def _scan_latest_log_for_work_dir(
    work_dir: Path, *, session_root: Path = SESSION_ROOT, scan_limit: int
) -> tuple[Optional[Path], Optional[str]]:
    """
    Scan ~/.codex/sessions and find the latest log whose session_meta.cwd is within work_dir.

    Uses a bounded heap so we only inspect the N most recently modified logs.
    """
    root = Path(session_root).expanduser()
    if not root.exists():
        return None, None

    work_dir_str = str(work_dir)

    heap: list[tuple[float, str]] = []
    try:
        for p in root.glob("**/*.jsonl"):
            if not p.is_file():
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
        cwd, sid = _read_session_meta(path)
        if not cwd:
            continue
        if _path_within(cwd, work_dir_str):
            return path, sid
    return None, None


def _should_overwrite_binding(current: Optional[Path], candidate: Path) -> bool:
    if not current:
        return True
    if not current.exists():
        return True
    try:
        return candidate.stat().st_mtime > current.stat().st_mtime
    except OSError:
        return True


def _refresh_codex_log_binding(
    session: CodexProjectSession,
    *,
    session_root: Path = SESSION_ROOT,
    scan_limit: int,
    force_scan: bool,
) -> bool:
    """
    Refresh .codex-session codex_session_id/codex_session_path.

    Priority:
      1) Parse session_id from start_cmd and bind to its log (preferred).
      2) Fallback scan latest log by work_dir (only when forced or when (1) fails).
    """
    current_log = Path(session.codex_session_path).expanduser() if session.codex_session_path else None

    intended_sid = _extract_session_id_from_start_cmd(session.start_cmd)
    intended_log: Optional[Path] = None
    if intended_sid:
        intended_log = _find_latest_log_for_session_id(intended_sid, session_root=session_root)
        if intended_log and intended_log.exists():
            if _should_overwrite_binding(current_log, intended_log) or session.codex_session_id != intended_sid:
                session.update_codex_log_binding(log_path=str(intended_log), session_id=intended_sid)
                return True
            return False

    need_scan = bool(force_scan or (not intended_sid) or (intended_sid and not intended_log))
    if not need_scan:
        return False

    candidate_log, candidate_sid = _scan_latest_log_for_work_dir(
        Path(session.work_dir), session_root=session_root, scan_limit=scan_limit
    )
    if not candidate_log or not candidate_log.exists():
        return False

    if _should_overwrite_binding(current_log, candidate_log) or (
        candidate_sid and candidate_sid != session.codex_session_id
    ):
        session.update_codex_log_binding(log_path=str(candidate_log), session_id=candidate_sid)
        return True
    return False


@dataclass
class _QueuedTask:
    request: CaskdRequest
    created_ms: int
    req_id: str
    done_event: threading.Event
    result: Optional[CaskdResult] = None


class _SessionWorker(BaseSessionWorker[_QueuedTask, CaskdResult]):
    def _handle_exception(self, exc: Exception, task: _QueuedTask) -> CaskdResult:
        write_log(log_path(CASKD_SPEC.log_file_name), f"[ERROR] session={self.session_key} req_id={task.req_id} {exc}")
        return CaskdResult(
            exit_code=1,
            reply=str(exc),
            req_id=task.req_id,
            session_key=self.session_key,
            log_path=None,
            anchor_seen=False,
            done_seen=False,
            fallback_scan=False,
        )

    def _handle_task(self, task: _QueuedTask) -> CaskdResult:
        started_ms = _now_ms()
        req = task.request
        work_dir = Path(req.work_dir)
        write_log(log_path(CASKD_SPEC.log_file_name), f"[INFO] start session={self.session_key} req_id={task.req_id} work_dir={req.work_dir}")
        session = load_project_session(work_dir)
        if not session:
            return CaskdResult(
                exit_code=1,
                reply="❌ No active Codex session found for work_dir. Run 'ccb codex' (or add codex to ccb.config) in that project first.",
                req_id=task.req_id,
                session_key=self.session_key,
                log_path=None,
                anchor_seen=False,
                done_seen=False,
                fallback_scan=False,
            )

        ok, pane_or_err = session.ensure_pane()
        if not ok:
            return CaskdResult(
                exit_code=1,
                reply=f"❌ Session pane not available: {pane_or_err}",
                req_id=task.req_id,
                session_key=self.session_key,
                log_path=None,
                anchor_seen=False,
                done_seen=False,
                fallback_scan=False,
            )
        pane_id = pane_or_err
        backend = get_backend_for_session(session.data)
        if not backend:
            return CaskdResult(
                exit_code=1,
                reply="❌ Terminal backend not available",
                req_id=task.req_id,
                session_key=self.session_key,
                log_path=None,
                anchor_seen=False,
                done_seen=False,
                fallback_scan=False,
            )

        prompt = wrap_codex_prompt(req.message, task.req_id)

        # Prefer project-bound log path if present; allow reader to follow newer logs if it changes.
        preferred_log = session.codex_session_path or None
        codex_session_id = session.codex_session_id or None
        # Start with session_id_filter if present; drop it if we see no events early (escape hatch).
        reader = CodexLogReader(log_path=preferred_log, session_id_filter=codex_session_id or None, work_dir=Path(session.work_dir))

        state = reader.capture_state()

        backend.send_text(pane_id, prompt)

        deadline = None if float(req.timeout_s) < 0.0 else (time.time() + float(req.timeout_s))
        chunks: list[str] = []
        anchor_seen = False
        done_seen = False
        anchor_ms: Optional[int] = None
        done_ms: Optional[int] = None
        fallback_scan = False

        # If we can't observe our user anchor within a short grace window, the log binding is likely stale.
        # In that case we drop the bound session filter and rebind to the latest log, starting from a tail
        # offset (NOT EOF) to avoid missing a reply that already landed.
        anchor_grace_deadline = min(deadline, time.time() + 1.5) if deadline is not None else (time.time() + 1.5)
        anchor_collect_grace = min(deadline, time.time() + 2.0) if deadline is not None else (time.time() + 2.0)
        rebounded = False
        saw_any_event = False
        tail_bytes = int(os.environ.get("CCB_CASKD_REBIND_TAIL_BYTES", str(1024 * 1024 * 2)) or (1024 * 1024 * 2))
        last_pane_check = time.time()
        # Windows平台降低检查频率，减少CLI调用和窗口闪烁风险
        default_interval = "5.0" if is_windows() else "2.0"
        pane_check_interval = float(os.environ.get("CCB_CASKD_PANE_CHECK_INTERVAL", default_interval) or default_interval)

        while True:
            if deadline is not None:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                wait_step = min(remaining, 0.5)
            else:
                wait_step = 0.5

            # Fail fast if the pane dies mid-request (e.g. Codex killed).
            if time.time() - last_pane_check >= pane_check_interval:
                try:
                    alive = bool(backend.is_alive(pane_id))
                except Exception:
                    alive = False
                if not alive:
                    write_log(log_path(CASKD_SPEC.log_file_name), f"[ERROR] Pane {pane_id} died during request session={self.session_key} req_id={task.req_id}")
                    codex_log_path = None
                    try:
                        lp = reader.current_log_path()
                        if lp:
                            codex_log_path = str(lp)
                    except Exception:
                        codex_log_path = None
                    return CaskdResult(
                        exit_code=1,
                        reply="❌ Codex pane died during request",
                        req_id=task.req_id,
                        session_key=self.session_key,
                        log_path=codex_log_path,
                        anchor_seen=anchor_seen,
                        done_seen=False,
                        fallback_scan=fallback_scan,
                        anchor_ms=anchor_ms,
                        done_ms=None,
                    )
                # Check for Codex interrupted state
                # Only trigger if "■ Conversation interrupted" appears AFTER "CCB_REQ_ID" (our request)
                # This ensures we're detecting interrupt for current task, not history
                if hasattr(backend, 'get_text'):
                    try:
                        pane_text = backend.get_text(pane_id, lines=15)
                        if pane_text and '■ Conversation interrupted' in pane_text:
                            # Verify this is for current request: interrupt should appear after our req_id
                            req_id_pos = pane_text.find(task.req_id)
                            interrupt_pos = pane_text.find('■ Conversation interrupted')
                            # Only trigger if interrupt is after our request ID (or if req_id not found but interrupt is recent)
                            is_current_interrupt = (req_id_pos >= 0 and interrupt_pos > req_id_pos) or (req_id_pos < 0 and interrupt_pos >= 0)
                        else:
                            is_current_interrupt = False
                        if is_current_interrupt:
                            write_log(log_path(CASKD_SPEC.log_file_name), f"[WARN] Codex interrupted - skipping task session={self.session_key} req_id={task.req_id}")
                            codex_log_path = None
                            try:
                                lp = reader.current_log_path()
                                if lp:
                                    codex_log_path = str(lp)
                            except Exception:
                                codex_log_path = None
                            return CaskdResult(
                                exit_code=1,
                                reply="❌ Codex interrupted. Please recover Codex manually, then retry. Skipping to next task.",
                                req_id=task.req_id,
                                session_key=self.session_key,
                                log_path=codex_log_path,
                                anchor_seen=anchor_seen,
                                done_seen=False,
                                fallback_scan=fallback_scan,
                                anchor_ms=anchor_ms,
                                done_ms=None,
                            )
                    except Exception:
                        pass
                last_pane_check = time.time()

            event, state = reader.wait_for_event(state, wait_step)
            if event is None:
                if (not rebounded) and (not anchor_seen) and time.time() >= anchor_grace_deadline and codex_session_id:
                    # Escape hatch: drop the session_id_filter so the reader can follow the latest log for this work_dir.
                    codex_session_id = None
                    reader = CodexLogReader(log_path=preferred_log, session_id_filter=None, work_dir=Path(session.work_dir))
                    log_hint = reader.current_log_path()
                    state = _tail_state_for_log(log_hint, tail_bytes=tail_bytes)
                    fallback_scan = True
                    rebounded = True
                continue

            role, text = event
            saw_any_event = True
            if role == "user":
                if f"{REQ_ID_PREFIX} {task.req_id}" in text:
                    anchor_seen = True
                    if anchor_ms is None:
                        anchor_ms = _now_ms() - started_ms
                continue

            if role != "assistant":
                continue

            # Avoid collecting unrelated assistant messages until our request is visible in logs.
            # Some Codex builds may omit user entries; after a short grace period, start collecting anyway.
            if (not anchor_seen) and time.time() < anchor_collect_grace:
                continue

            chunks.append(text)
            combined = "\n".join(chunks)
            if is_done_text(combined, task.req_id):
                done_seen = True
                done_ms = _now_ms() - started_ms
                break

        combined = "\n".join(chunks)
        reply = strip_done_text(combined, task.req_id)
        codex_log_path = None
        try:
            lp = state.get("log_path")
            if lp:
                codex_log_path = str(lp)
        except Exception:
            codex_log_path = None

        if done_seen and codex_log_path:
            sid = _extract_codex_session_id_from_log(Path(codex_log_path))
            session.update_codex_log_binding(log_path=codex_log_path, session_id=sid)

        exit_code = 0 if done_seen else 2
        result = CaskdResult(
            exit_code=exit_code,
            reply=reply,
            req_id=task.req_id,
            session_key=self.session_key,
            log_path=codex_log_path,
            anchor_seen=anchor_seen,
            done_seen=done_seen,
            fallback_scan=fallback_scan,
            anchor_ms=anchor_ms,
            done_ms=done_ms,
        )
        write_log(log_path(CASKD_SPEC.log_file_name), 
            f"[INFO] done session={self.session_key} req_id={task.req_id} exit={result.exit_code} "
            f"anchor={result.anchor_seen} done={result.done_seen} fallback={result.fallback_scan} "
            f"log={result.log_path or ''} anchor_ms={result.anchor_ms or ''} done_ms={result.done_ms or ''}"
        )
        return result


@dataclass
class _SessionEntry:
    work_dir: Path
    session: Optional[CodexProjectSession]
    session_file: Optional[Path]
    file_mtime: float
    last_check: float
    valid: bool = True
    next_bind_refresh: float = 0.0
    bind_backoff_s: float = 0.0


class SessionRegistry:
    """Manages and monitors all active Codex sessions."""

    CHECK_INTERVAL = 10.0  # seconds between validity checks

    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: dict[str, _SessionEntry] = {}  # work_dir -> entry
        self._stop = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None

    def start_monitor(self) -> None:
        if self._monitor_thread is None:
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()

    def stop_monitor(self) -> None:
        self._stop.set()

    def get_session(self, work_dir: Path) -> Optional[CodexProjectSession]:
        key = str(work_dir)
        with self._lock:
            entry = self._sessions.get(key)
            if entry:
                # If the session entry is invalid but the session file was updated (e.g. new pane info),
                # reload and re-validate so we can recover.
                session_file = entry.session_file or find_project_session_file(work_dir) or (work_dir / ".ccb_config" / ".codex-session")
                if session_file.exists():
                    try:
                        current_mtime = session_file.stat().st_mtime
                        if (not entry.session_file) or (session_file != entry.session_file) or (current_mtime != entry.file_mtime):
                            write_log(log_path(CASKD_SPEC.log_file_name), f"[INFO] Session file changed, reloading: {work_dir}")
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

    def _load_and_cache(self, work_dir: Path) -> Optional[_SessionEntry]:
        session = load_project_session(work_dir)
        session_file = session.session_file if session else (find_project_session_file(work_dir) or (work_dir / ".ccb_config" / ".codex-session"))
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
                write_log(log_path(CASKD_SPEC.log_file_name), f"[INFO] Session invalidated: {work_dir}")

    def remove(self, work_dir: Path) -> None:
        key = str(work_dir)
        with self._lock:
            if key in self._sessions:
                del self._sessions[key]
                write_log(log_path(CASKD_SPEC.log_file_name), f"[INFO] Session removed: {work_dir}")

    def _monitor_loop(self) -> None:
        while not self._stop.wait(self.CHECK_INTERVAL):
            self._check_all_sessions()

    def _check_all_sessions(self) -> None:
        now = time.time()
        refresh_interval_s = _env_float("CCB_CASKD_BIND_REFRESH_INTERVAL", 60.0)
        scan_limit = max(50, min(20000, _env_int("CCB_CASKD_BIND_SCAN_LIMIT", _env_int("CCB_CODEX_SCAN_LIMIT", 400))))

        with self._lock:
            snapshot = [(key, entry.work_dir) for key, entry in self._sessions.items() if entry.valid]

        for key, work_dir in snapshot:
            try:
                self._check_one(key, work_dir, now=now, refresh_interval_s=refresh_interval_s, scan_limit=scan_limit)
            except Exception:
                # Never let monitor crash the daemon.
                continue

        # Cleanup invalid entries.
        with self._lock:
            keys_to_remove: list[str] = []
            for key, entry in list(self._sessions.items()):
                if not entry.valid and now - entry.last_check > 300:
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._sessions[key]

    def _check_one(self, key: str, work_dir: Path, *, now: float, refresh_interval_s: float, scan_limit: int) -> None:
        # Reload on session file changes (mtime) so we can pick up start_cmd/session_id changes.
        session_file = find_project_session_file(work_dir) or (work_dir / ".ccb_config" / ".codex-session")
        try:
            exists = session_file.exists()
        except Exception:
            exists = False

        if not exists:
            with self._lock:
                entry = self._sessions.get(key)
                if entry and entry.valid:
                    write_log(log_path(CASKD_SPEC.log_file_name), f"[WARN] Session file deleted: {work_dir}")
                    entry.valid = False
                    entry.last_check = now
            return

        try:
            current_mtime = session_file.stat().st_mtime
        except Exception:
            current_mtime = 0.0

        session: Optional[CodexProjectSession] = None
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

        # Ensure pane is still alive.
        try:
            ok, _ = session.ensure_pane()
        except Exception:
            ok = False
        if not ok:
            with self._lock:
                entry2 = self._sessions.get(key)
                if entry2 and entry2.valid:
                    write_log(log_path(CASKD_SPEC.log_file_name), f"[WARN] Session pane invalid: {work_dir}")
                    entry2.valid = False
                    entry2.last_check = now
            return

        # Refresh codex log binding periodically, and immediately after session file changes.
        with self._lock:
            entry3 = self._sessions.get(key)
            if not entry3 or not entry3.valid:
                return
            due = now >= (entry3.next_bind_refresh or 0.0)
            if not due and not file_changed:
                entry3.last_check = now
                return
            backoff = entry3.bind_backoff_s or refresh_interval_s

        force_scan = bool(file_changed)  # if session file changed, make a best-effort full refresh
        updated = False
        try:
            updated = _refresh_codex_log_binding(
                session,
                session_root=SESSION_ROOT,
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
            # Refresh session_file mtime after potential write-back.
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


_session_registry: Optional[SessionRegistry] = None


def get_session_registry() -> SessionRegistry:
    global _session_registry
    if _session_registry is None:
        _session_registry = SessionRegistry()
        _session_registry.start_monitor()
    return _session_registry


class _WorkerPool:
    def __init__(self):
        self._pool = PerSessionWorkerPool[_SessionWorker]()

    def submit(self, request: CaskdRequest) -> _QueuedTask:
        req_id = make_req_id()
        task = _QueuedTask(request=request, created_ms=_now_ms(), req_id=req_id, done_event=threading.Event())

        session = load_project_session(Path(request.work_dir))
        session_key = compute_session_key(session) if session else "codex:unknown"

        worker = self._pool.get_or_create(session_key, _SessionWorker)
        worker.enqueue(task)
        return task


class CaskdServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0, *, state_file: Optional[Path] = None):
        self.host = host
        self.port = port
        self.state_file = state_file or state_file_path(CASKD_SPEC.state_file_name)
        self.token = random_token()
        self.pool = _WorkerPool()

    def serve_forever(self) -> int:
        def _handle_request(msg: dict) -> dict:
            try:
                req = CaskdRequest(
                    client_id=str(msg.get("id") or ""),
                    work_dir=str(msg.get("work_dir") or ""),
                    timeout_s=float(msg.get("timeout_s") or 300.0),
                    quiet=bool(msg.get("quiet") or False),
                    message=str(msg.get("message") or ""),
                    output_path=str(msg.get("output_path")) if msg.get("output_path") else None,
                )
            except Exception as exc:
                return {"type": "cask.response", "v": 1, "id": msg.get("id"), "exit_code": 1, "reply": f"Bad request: {exc}"}

            task = self.pool.submit(req)
            wait_timeout = None if float(req.timeout_s) < 0.0 else (float(req.timeout_s) + 5.0)
            task.done_event.wait(timeout=wait_timeout)
            result = task.result
            if not result:
                return {"type": "cask.response", "v": 1, "id": req.client_id, "exit_code": 2, "reply": ""}

            return {
                "type": "cask.response",
                "v": 1,
                "id": req.client_id,
                "req_id": result.req_id,
                "exit_code": result.exit_code,
                "reply": result.reply,
                "meta": {
                    "session_key": result.session_key,
                    "log_path": result.log_path,
                    "anchor_seen": result.anchor_seen,
                    "done_seen": result.done_seen,
                    "fallback_scan": result.fallback_scan,
                    "anchor_ms": result.anchor_ms,
                    "done_ms": result.done_ms,
                },
            }

        server = AskDaemonServer(
            spec=CASKD_SPEC,
            host=self.host,
            port=self.port,
            token=self.token,
            state_file=self.state_file,
            request_handler=_handle_request,
            request_queue_size=128,
            on_stop=self._cleanup_state_file,
        )
        return server.serve_forever()

    def _cleanup_state_file(self) -> None:
        try:
            st = read_state(self.state_file)
        except Exception:
            st = None
        try:
            if isinstance(st, dict) and int(st.get("pid") or 0) == os.getpid():
                self.state_file.unlink(missing_ok=True)  # py3.8+: missing_ok
        except TypeError:
            try:
                if isinstance(st, dict) and int(st.get("pid") or 0) == os.getpid() and self.state_file.exists():
                    self.state_file.unlink()
            except Exception:
                pass
        except Exception:
            pass


def read_state(state_file: Optional[Path] = None) -> Optional[dict]:
    state_file = state_file or state_file_path(CASKD_SPEC.state_file_name)
    return askd_rpc.read_state(state_file)


def ping_daemon(timeout_s: float = 0.5, state_file: Optional[Path] = None) -> bool:
    state_file = state_file or state_file_path(CASKD_SPEC.state_file_name)
    return askd_rpc.ping_daemon("cask", timeout_s, state_file)


def shutdown_daemon(timeout_s: float = 1.0, state_file: Optional[Path] = None) -> bool:
    state_file = state_file or state_file_path(CASKD_SPEC.state_file_name)
    return askd_rpc.shutdown_daemon("cask", timeout_s, state_file)
