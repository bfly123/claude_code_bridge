from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from worker_pool import BaseSessionWorker, PerSessionWorkerPool

from claude_comm import ClaudeLogReader
from ccb_protocol import REQ_ID_PREFIX
from laskd_protocol import (
    LaskdRequest,
    LaskdResult,
    is_done_text,
    make_req_id,
    strip_done_text,
    wrap_claude_prompt,
)
from laskd_session import compute_session_key, load_project_session
from laskd_registry import get_session_registry
from pane_registry import upsert_registry
from project_id import compute_ccb_project_id
from terminal import get_backend_for_session
from askd_runtime import state_file_path, log_path, write_log, random_token
import askd_rpc
from askd_server import AskDaemonServer
from providers import LASKD_SPEC


def _now_ms() -> int:
    return int(time.time() * 1000)


def _write_log(line: str) -> None:
    write_log(log_path(LASKD_SPEC.log_file_name), line)


def _tail_state_for_log(log_path: Optional[Path], *, tail_bytes: int) -> dict:
    if not log_path or not log_path.exists():
        return {"session_path": log_path if log_path else None, "offset": 0, "carry": b""}
    try:
        size = log_path.stat().st_size
    except OSError:
        size = 0
    offset = max(0, size - max(0, int(tail_bytes)))
    return {"session_path": log_path, "offset": offset, "carry": b""}


@dataclass
class _QueuedTask:
    request: LaskdRequest
    created_ms: int
    req_id: str
    done_event: threading.Event
    result: Optional[LaskdResult] = None


class _SessionWorker(BaseSessionWorker[_QueuedTask, LaskdResult]):
    def _handle_exception(self, exc: Exception, task: _QueuedTask) -> LaskdResult:
        _write_log(f"[ERROR] session={self.session_key} req_id={task.req_id} {exc}")
        return LaskdResult(
            exit_code=1,
            reply=str(exc),
            req_id=task.req_id,
            session_key=self.session_key,
            done_seen=False,
            done_ms=None,
            anchor_seen=False,
            fallback_scan=False,
            anchor_ms=None,
        )

    def _handle_task(self, task: _QueuedTask) -> LaskdResult:
        started_ms = _now_ms()
        req = task.request
        work_dir = Path(req.work_dir)
        _write_log(f"[INFO] start session={self.session_key} req_id={task.req_id} work_dir={req.work_dir}")

        session = load_project_session(work_dir)
        if not session:
            return LaskdResult(
                exit_code=1,
                reply="❌ No active Claude session found for work_dir. Run 'ccb claude' (or add claude to ccb.config) in that project first.",
                req_id=task.req_id,
                session_key=self.session_key,
                done_seen=False,
                done_ms=None,
                anchor_seen=False,
                fallback_scan=False,
                anchor_ms=None,
            )

        ok, pane_or_err = session.ensure_pane()
        if not ok:
            return LaskdResult(
                exit_code=1,
                reply=f"❌ Session pane not available: {pane_or_err}",
                req_id=task.req_id,
                session_key=self.session_key,
                done_seen=False,
                done_ms=None,
                anchor_seen=False,
                fallback_scan=False,
                anchor_ms=None,
            )
        pane_id = pane_or_err

        backend = get_backend_for_session(session.data)
        if not backend:
            return LaskdResult(
                exit_code=1,
                reply="❌ Terminal backend not available",
                req_id=task.req_id,
                session_key=self.session_key,
                done_seen=False,
                done_ms=None,
                anchor_seen=False,
                fallback_scan=False,
                anchor_ms=None,
            )

        log_reader = ClaudeLogReader(work_dir=Path(session.work_dir))
        if session.claude_session_path:
            try:
                log_reader.set_preferred_session(Path(session.claude_session_path))
            except Exception:
                pass
        state = log_reader.capture_state()

        prompt = wrap_claude_prompt(req.message, task.req_id)
        backend.send_text(pane_id, prompt)

        deadline = None if float(req.timeout_s) < 0.0 else (time.time() + float(req.timeout_s))
        chunks: list[str] = []
        anchor_seen = False
        fallback_scan = False
        anchor_ms: int | None = None
        done_seen = False
        done_ms: int | None = None
        anchor_grace_deadline = min(deadline, time.time() + 1.5) if deadline is not None else (time.time() + 1.5)
        anchor_collect_grace = min(deadline, time.time() + 2.0) if deadline is not None else (time.time() + 2.0)
        rebounded = False
        tail_bytes = int(os.environ.get("CCB_LASKD_REBIND_TAIL_BYTES", str(1024 * 1024 * 2)) or (1024 * 1024 * 2))

        pane_check_interval = float(os.environ.get("CCB_LASKD_PANE_CHECK_INTERVAL", "2.0") or "2.0")
        last_pane_check = time.time()

        while True:
            if deadline is not None:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                wait_step = min(remaining, 0.5)
            else:
                wait_step = 0.5

            if time.time() - last_pane_check >= pane_check_interval:
                try:
                    alive = bool(backend.is_alive(pane_id))
                except Exception:
                    alive = False
                if not alive:
                    _write_log(f"[ERROR] Pane {pane_id} died during request session={self.session_key} req_id={task.req_id}")
                    return LaskdResult(
                        exit_code=1,
                        reply="❌ Claude pane died during request",
                        req_id=task.req_id,
                        session_key=self.session_key,
                        done_seen=False,
                        done_ms=None,
                        anchor_seen=anchor_seen,
                        fallback_scan=fallback_scan,
                        anchor_ms=anchor_ms,
                    )

                if hasattr(backend, "get_text"):
                    try:
                        pane_text = backend.get_text(pane_id, lines=15)
                        if pane_text and "■ Conversation interrupted" in pane_text:
                            req_id_pos = pane_text.find(task.req_id)
                            interrupt_pos = pane_text.find("■ Conversation interrupted")
                            is_current = (req_id_pos >= 0 and interrupt_pos > req_id_pos) or (
                                req_id_pos < 0 and interrupt_pos >= 0
                            )
                            if is_current:
                                return LaskdResult(
                                    exit_code=1,
                                    reply="❌ Claude interrupted",
                                    req_id=task.req_id,
                                    session_key=self.session_key,
                                    done_seen=False,
                                    done_ms=None,
                                    anchor_seen=anchor_seen,
                                    fallback_scan=fallback_scan,
                                    anchor_ms=anchor_ms,
                                )
                    except Exception:
                        pass
                last_pane_check = time.time()

            events, state = log_reader.wait_for_events(state, wait_step)
            if not events:
                if (not rebounded) and (not anchor_seen) and time.time() >= anchor_grace_deadline:
                    log_reader = ClaudeLogReader(work_dir=Path(session.work_dir), use_sessions_index=False)
                    log_hint = log_reader.current_session_path()
                    state = _tail_state_for_log(log_hint, tail_bytes=tail_bytes)
                    fallback_scan = True
                    rebounded = True
                continue

            for role, text in events:
                if role == "user":
                    if f"{REQ_ID_PREFIX} {task.req_id}" in text:
                        anchor_seen = True
                        if anchor_ms is None:
                            anchor_ms = _now_ms() - started_ms
                    continue
                if role != "assistant":
                    continue
                if (not anchor_seen) and time.time() < anchor_collect_grace:
                    continue
                chunks.append(text)
                combined = "\n".join(chunks)
                if is_done_text(combined, task.req_id):
                    done_seen = True
                    done_ms = _now_ms() - started_ms
                    break

            if done_seen:
                break

        combined = "\n".join(chunks)
        final_reply = strip_done_text(combined, task.req_id)

        if done_seen:
            session_path = state.get("session_path") if isinstance(state, dict) else None
            session_id = None
            if isinstance(session_path, Path):
                session_id = session_path.stem
            session.update_claude_binding(session_path=session_path if isinstance(session_path, Path) else None, session_id=session_id)
            try:
                ccb_pid = str(session.data.get("ccb_project_id") or "").strip()
                if not ccb_pid:
                    ccb_pid = compute_ccb_project_id(Path(session.work_dir))
                ccb_session_id = str(session.data.get("ccb_session_id") or "").strip()
                if ccb_session_id:
                    upsert_registry(
                        {
                            "ccb_session_id": ccb_session_id,
                            "ccb_project_id": ccb_pid or None,
                            "work_dir": str(session.work_dir),
                            "terminal": session.terminal,
                            "providers": {
                                "claude": {
                                    "pane_id": session.pane_id or None,
                                    "pane_title_marker": session.pane_title_marker or None,
                                    "session_file": str(session.session_file),
                                    "claude_session_id": session.data.get("claude_session_id"),
                                    "claude_session_path": session.data.get("claude_session_path"),
                                }
                            },
                        }
                    )
            except Exception:
                pass
            try:
                get_session_registry().register_session(Path(session.work_dir), session)
            except Exception:
                pass

        result = LaskdResult(
            exit_code=0 if done_seen else 2,
            reply=final_reply,
            req_id=task.req_id,
            session_key=self.session_key,
            done_seen=done_seen,
            done_ms=done_ms,
            anchor_seen=anchor_seen,
            fallback_scan=fallback_scan,
            anchor_ms=anchor_ms,
        )
        _write_log(
            f"[INFO] done session={self.session_key} req_id={task.req_id} exit={result.exit_code} "
            f"anchor={result.anchor_seen} done={result.done_seen} fallback={result.fallback_scan} "
            f"anchor_ms={result.anchor_ms or ''} done_ms={result.done_ms or ''}"
        )
        return result


class _WorkerPool:
    def __init__(self):
        self._pool = PerSessionWorkerPool[_SessionWorker]()

    def submit(self, request: LaskdRequest) -> _QueuedTask:
        req_id = make_req_id()
        task = _QueuedTask(request=request, created_ms=_now_ms(), req_id=req_id, done_event=threading.Event())

        session = load_project_session(Path(request.work_dir))
        session_key = compute_session_key(session) if session else "claude:unknown"

        worker = self._pool.get_or_create(session_key, _SessionWorker)
        worker.enqueue(task)
        return task


class LaskdServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0, *, state_file: Optional[Path] = None):
        self.host = host
        self.port = port
        self.state_file = state_file or state_file_path(LASKD_SPEC.state_file_name)
        self.token = random_token()
        self.pool = _WorkerPool()

    def serve_forever(self) -> int:
        def _handle_request(msg: dict) -> dict:
            try:
                req = LaskdRequest(
                    client_id=str(msg.get("id") or ""),
                    work_dir=str(msg.get("work_dir") or ""),
                    timeout_s=float(msg.get("timeout_s") or 300.0),
                    quiet=bool(msg.get("quiet") or False),
                    message=str(msg.get("message") or ""),
                    output_path=str(msg.get("output_path")) if msg.get("output_path") else None,
                )
            except Exception as exc:
                return {"type": "lask.response", "v": 1, "id": msg.get("id"), "exit_code": 1, "reply": f"Bad request: {exc}"}

            task = self.pool.submit(req)
            wait_timeout = None if float(req.timeout_s) < 0.0 else (float(req.timeout_s) + 5.0)
            task.done_event.wait(timeout=wait_timeout)
            result = task.result
            if not result:
                return {"type": "lask.response", "v": 1, "id": req.client_id, "exit_code": 2, "reply": ""}

            return {
                "type": "lask.response",
                "v": 1,
                "id": req.client_id,
                "req_id": result.req_id,
                "exit_code": result.exit_code,
                "reply": result.reply,
                "meta": {
                    "session_key": result.session_key,
                    "done_seen": result.done_seen,
                    "done_ms": result.done_ms,
                    "anchor_seen": result.anchor_seen,
                    "fallback_scan": result.fallback_scan,
                    "anchor_ms": result.anchor_ms,
                },
            }

        server = AskDaemonServer(
            spec=LASKD_SPEC,
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
                self.state_file.unlink(missing_ok=True)
        except TypeError:
            try:
                if isinstance(st, dict) and int(st.get("pid") or 0) == os.getpid() and self.state_file.exists():
                    self.state_file.unlink()
            except Exception:
                pass
        except Exception:
            pass


def read_state(state_file: Optional[Path] = None) -> Optional[dict]:
    state_file = state_file or state_file_path(LASKD_SPEC.state_file_name)
    return askd_rpc.read_state(state_file)


def ping_daemon(timeout_s: float = 0.5, state_file: Optional[Path] = None) -> bool:
    state_file = state_file or state_file_path(LASKD_SPEC.state_file_name)
    return askd_rpc.ping_daemon("lask", timeout_s, state_file)


def shutdown_daemon(timeout_s: float = 1.0, state_file: Optional[Path] = None) -> bool:
    state_file = state_file or state_file_path(LASKD_SPEC.state_file_name)
    return askd_rpc.shutdown_daemon("lask", timeout_s, state_file)
