from __future__ import annotations

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
from codex_comm import CodexLogReader, CodexCommunicator
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
                reply="❌ No active Codex session found for work_dir. Run 'ccb up codex' in that project first.",
                req_id=task.req_id,
                session_key=self.session_key,
                log_path=None,
                anchor_seen=False,
                done_seen=False,
                fallback_scan=False,
            )

        if session.terminal not in ("wezterm", "iterm2"):
            return CaskdResult(
                exit_code=1,
                reply=f"❌ caskd currently supports WezTerm/iTerm2 sessions only (got terminal={session.terminal}).",
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

        deadline = time.time() + float(req.timeout_s)
        chunks: list[str] = []
        anchor_seen = False
        done_seen = False
        anchor_ms: Optional[int] = None
        done_ms: Optional[int] = None
        fallback_scan = False

        # If we can't observe our user anchor within a short grace window, the log binding is likely stale.
        # In that case we drop the bound session filter and rebind to the latest log, starting from a tail
        # offset (NOT EOF) to avoid missing a reply that already landed.
        anchor_grace_deadline = min(deadline, time.time() + 1.5)
        anchor_collect_grace = min(deadline, time.time() + 2.0)
        rebounded = False
        saw_any_event = False
        tail_bytes = int(os.environ.get("CCB_CASKD_REBIND_TAIL_BYTES", str(1024 * 1024 * 2)) or (1024 * 1024 * 2))
        last_pane_check = time.time()
        pane_check_interval = float(os.environ.get("CCB_CASKD_PANE_CHECK_INTERVAL", "2.0") or "2.0")

        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                break

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

            event, state = reader.wait_for_event(state, min(remaining, 0.5))
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
                session_file = entry.session_file or find_project_session_file(work_dir) or (work_dir / ".codex-session")
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
        session_file = session.session_file if session else (find_project_session_file(work_dir) or (work_dir / ".codex-session"))
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
        with self._lock:
            keys_to_remove = []
            for key, entry in self._sessions.items():
                if not entry.valid:
                    continue
                if entry.session_file and not entry.session_file.exists():
                    write_log(log_path(CASKD_SPEC.log_file_name), f"[WARN] Session file deleted: {entry.work_dir}")
                    entry.valid = False
                    continue
                if entry.session:
                    ok, _ = entry.session.ensure_pane()
                    if not ok:
                        write_log(log_path(CASKD_SPEC.log_file_name), f"[WARN] Session pane invalid: {entry.work_dir}")
                        entry.valid = False
                entry.last_check = time.time()
            for key, entry in list(self._sessions.items()):
                if not entry.valid and time.time() - entry.last_check > 300:
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._sessions[key]

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
            task.done_event.wait(timeout=req.timeout_s + 5.0)
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
        )
        return server.serve_forever()


def read_state(state_file: Optional[Path] = None) -> Optional[dict]:
    state_file = state_file or state_file_path(CASKD_SPEC.state_file_name)
    return askd_rpc.read_state(state_file)


def ping_daemon(timeout_s: float = 0.5, state_file: Optional[Path] = None) -> bool:
    state_file = state_file or state_file_path(CASKD_SPEC.state_file_name)
    return askd_rpc.ping_daemon("cask", timeout_s, state_file)


def shutdown_daemon(timeout_s: float = 1.0, state_file: Optional[Path] = None) -> bool:
    state_file = state_file or state_file_path(CASKD_SPEC.state_file_name)
    return askd_rpc.shutdown_daemon("cask", timeout_s, state_file)
