from __future__ import annotations

import json
import os
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from oaskd_protocol import OaskdRequest, OaskdResult, is_done_text, make_req_id, strip_done_text, wrap_opencode_prompt
from oaskd_session import compute_session_key, load_project_session
from opencode_comm import OpenCodeLogReader
from process_lock import ProviderLock
from terminal import get_backend_for_session
from askd_runtime import state_file_path, log_path, write_log, random_token
from env_utils import env_bool
import askd_rpc
from askd_server import AskDaemonServer
from providers import OASKD_SPEC


def _now_ms() -> int:
    return int(time.time() * 1000)


def _cancel_detection_enabled(default: bool = False) -> bool:
    # Disabled by default for stability: OpenCode cancellation is session-scoped and hard to
    # attribute to a specific queued task without false positives.
    return env_bool("CCB_OASKD_CANCEL_DETECT", default)


def _tail_state_for_session(log_reader: OpenCodeLogReader) -> dict:
    # OpenCode reader uses storage files, not an append-only log; a fresh capture_state is enough.
    return log_reader.capture_state()


@dataclass
class _QueuedTask:
    request: OaskdRequest
    created_ms: int
    req_id: str
    done_event: threading.Event
    result: Optional[OaskdResult] = None


class _SessionWorker(threading.Thread):
    def __init__(self, session_key: str):
        super().__init__(daemon=True)
        self.session_key = session_key
        self._q: "queue.Queue[_QueuedTask]" = queue.Queue()
        self._stop = threading.Event()

    def enqueue(self, task: _QueuedTask) -> None:
        self._q.put(task)

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                task = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                task.result = self._handle_task(task)
            except Exception as exc:
                write_log(log_path(OASKD_SPEC.log_file_name), f"[ERROR] session={self.session_key} req_id={task.req_id} {exc}")
                task.result = OaskdResult(
                    exit_code=1,
                    reply=str(exc),
                    req_id=task.req_id,
                    session_key=self.session_key,
                    done_seen=False,
                    done_ms=None,
                )
            finally:
                task.done_event.set()

    def _handle_task(self, task: _QueuedTask) -> OaskdResult:
        started_ms = _now_ms()
        req = task.request
        work_dir = Path(req.work_dir)
        write_log(log_path(OASKD_SPEC.log_file_name), f"[INFO] start session={self.session_key} req_id={task.req_id} work_dir={req.work_dir}")

        # Cross-process serialization: if another client falls back to direct mode, it uses the same
        # per-session ProviderLock ("opencode", cwd=f"session:{session_key}"). Without this, daemon and
        # direct-mode requests can interleave in the same OpenCode pane and cause reply mismatches/hangs.
        lock_timeout = min(300.0, max(1.0, float(req.timeout_s)))
        lock = ProviderLock("opencode", cwd=f"session:{self.session_key}", timeout=lock_timeout)
        if not lock.acquire():
            return OaskdResult(
                exit_code=1,
                reply="❌ Another OpenCode request is in progress (session lock timeout).",
                req_id=task.req_id,
                session_key=self.session_key,
                done_seen=False,
                done_ms=None,
            )

        try:
            session = load_project_session(work_dir)
            if not session:
                return OaskdResult(
                    exit_code=1,
                    reply="❌ No active OpenCode session found for work_dir. Run 'ccb up opencode' in that project first.",
                    req_id=task.req_id,
                    session_key=self.session_key,
                    done_seen=False,
                    done_ms=None,
                )

            ok, pane_or_err = session.ensure_pane()
            if not ok:
                return OaskdResult(
                    exit_code=1,
                    reply=f"❌ Session pane not available: {pane_or_err}",
                    req_id=task.req_id,
                    session_key=self.session_key,
                    done_seen=False,
                    done_ms=None,
                )
            pane_id = pane_or_err

            backend = get_backend_for_session(session.data)
            if not backend:
                return OaskdResult(
                    exit_code=1,
                    reply="❌ Terminal backend not available",
                    req_id=task.req_id,
                    session_key=self.session_key,
                    done_seen=False,
                    done_ms=None,
                )

            log_reader = OpenCodeLogReader(work_dir=Path(session.work_dir), session_id_filter=(session.session_id or None))
            state = _tail_state_for_session(log_reader)
            cancel_enabled = _cancel_detection_enabled(False)
            session_id = state.get("session_id") if cancel_enabled and isinstance(state.get("session_id"), str) else None
            cancel_cursor = log_reader.open_cancel_log_cursor() if cancel_enabled and session_id else None
            cancel_since_s = time.time() if cancel_enabled else 0.0

            prompt = wrap_opencode_prompt(req.message, task.req_id)
            backend.send_text(pane_id, prompt)

            deadline = time.time() + float(req.timeout_s)
            chunks: list[str] = []
            done_seen = False
            done_ms: int | None = None

            pane_check_interval = float(os.environ.get("CCB_OASKD_PANE_CHECK_INTERVAL", "2.0") or "2.0")
            last_pane_check = time.time()

            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break

                if time.time() - last_pane_check >= pane_check_interval:
                    try:
                        alive = bool(backend.is_alive(pane_id))
                    except Exception:
                        alive = False
                    if not alive:
                        write_log(log_path(OASKD_SPEC.log_file_name), f"[ERROR] Pane {pane_id} died during request session={self.session_key} req_id={task.req_id}")
                        return OaskdResult(
                            exit_code=1,
                            reply="❌ OpenCode pane died during request",
                            req_id=task.req_id,
                            session_key=self.session_key,
                            done_seen=False,
                            done_ms=None,
                        )
                    last_pane_check = time.time()

                reply, state = log_reader.wait_for_message(state, min(remaining, 1.0))

                # Detect user cancellation using OpenCode server logs (handles the race where storage isn't updated).
                if cancel_enabled and session_id and cancel_cursor is not None:
                    try:
                        cancelled_log, cancel_cursor = log_reader.detect_cancel_event_in_logs(
                            cancel_cursor, session_id=session_id, since_epoch_s=cancel_since_s
                        )
                        if cancelled_log:
                            write_log(log_path(OASKD_SPEC.log_file_name), 
                                f"[WARN] OpenCode request cancelled (log) - skipping task session={self.session_key} req_id={task.req_id}"
                            )
                            return OaskdResult(
                                exit_code=1,
                                reply="❌ OpenCode request cancelled. Skipping to next task.",
                                req_id=task.req_id,
                                session_key=self.session_key,
                                done_seen=False,
                                done_ms=None,
                            )
                    except Exception:
                        pass

                # Detect user cancellation (OpenCode writes an assistant message with MessageAbortedError).
                #
                # Important: do NOT advance the caller's state baseline when not cancelled.
                # OpenCode may create an assistant message early (streaming), then later mark the SAME message
                # as aborted; if we update state.assistant_count here, we'd stop scanning that message.
                if cancel_enabled:
                    try:
                        cancelled, _new_state = log_reader.detect_cancelled_since(state, req_id=task.req_id)
                        if cancelled:
                            write_log(log_path(OASKD_SPEC.log_file_name), 
                                f"[WARN] OpenCode request cancelled - skipping task session={self.session_key} req_id={task.req_id}"
                            )
                            return OaskdResult(
                                exit_code=1,
                                reply="❌ OpenCode request cancelled. Skipping to next task.",
                                req_id=task.req_id,
                                session_key=self.session_key,
                                done_seen=False,
                                done_ms=None,
                            )
                    except Exception:
                        pass

                if not reply:
                    continue
                chunks.append(reply)
                combined = "\n".join(chunks)
                if is_done_text(combined, task.req_id):
                    done_seen = True
                    done_ms = _now_ms() - started_ms
                    break

            combined = "\n".join(chunks)
            final_reply = strip_done_text(combined, task.req_id)

            return OaskdResult(
                exit_code=0 if done_seen else 2,
                reply=final_reply,
                req_id=task.req_id,
                session_key=self.session_key,
                done_seen=done_seen,
                done_ms=done_ms,
            )
        finally:
            lock.release()


class _WorkerPool:
    def __init__(self):
        self._lock = threading.Lock()
        self._workers: dict[str, _SessionWorker] = {}

    def submit(self, request: OaskdRequest) -> _QueuedTask:
        req_id = make_req_id()
        task = _QueuedTask(request=request, created_ms=_now_ms(), req_id=req_id, done_event=threading.Event())

        session = load_project_session(Path(request.work_dir))
        session_key = compute_session_key(session) if session else "opencode:unknown"

        with self._lock:
            worker = self._workers.get(session_key)
            if worker is None:
                worker = _SessionWorker(session_key)
                self._workers[session_key] = worker
                worker.start()

        worker.enqueue(task)
        try:
            qsize = int(worker._q.qsize())
        except Exception:
            qsize = -1
        write_log(log_path(OASKD_SPEC.log_file_name), f"[INFO] enqueued session={session_key} req_id={req_id} qsize={qsize} client_id={request.client_id}")
        return task


class OaskdServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0, *, state_file: Optional[Path] = None):
        self.host = host
        self.port = port
        self.state_file = state_file or state_file_path(OASKD_SPEC.state_file_name)
        self.token = random_token()
        self.pool = _WorkerPool()

    def serve_forever(self) -> int:
        def _handle_request(msg: dict) -> dict:
            try:
                req = OaskdRequest(
                    client_id=str(msg.get("id") or ""),
                    work_dir=str(msg.get("work_dir") or ""),
                    timeout_s=float(msg.get("timeout_s") or 300.0),
                    quiet=bool(msg.get("quiet") or False),
                    message=str(msg.get("message") or ""),
                    output_path=str(msg.get("output_path")) if msg.get("output_path") else None,
                )
            except Exception as exc:
                return {"type": "oask.response", "v": 1, "id": msg.get("id"), "exit_code": 1, "reply": f"Bad request: {exc}"}

            write_log(
                log_path(OASKD_SPEC.log_file_name),
                f"[INFO] recv client_id={req.client_id} work_dir={req.work_dir} timeout_s={int(req.timeout_s)} msg_len={len(req.message)}",
            )
            task = self.pool.submit(req)
            task.done_event.wait(timeout=req.timeout_s + 5.0)
            result = task.result
            if not result:
                return {"type": "oask.response", "v": 1, "id": req.client_id, "exit_code": 2, "reply": ""}

            return {
                "type": "oask.response",
                "v": 1,
                "id": req.client_id,
                "req_id": result.req_id,
                "exit_code": result.exit_code,
                "reply": result.reply,
                "meta": {
                    "session_key": result.session_key,
                    "done_seen": result.done_seen,
                    "done_ms": result.done_ms,
                },
            }

        server = AskDaemonServer(
            spec=OASKD_SPEC,
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
    state_file = state_file or state_file_path(OASKD_SPEC.state_file_name)
    return askd_rpc.read_state(state_file)


def ping_daemon(timeout_s: float = 0.5, state_file: Optional[Path] = None) -> bool:
    state_file = state_file or state_file_path(OASKD_SPEC.state_file_name)
    return askd_rpc.ping_daemon("oask", timeout_s, state_file)


def shutdown_daemon(timeout_s: float = 1.0, state_file: Optional[Path] = None) -> bool:
    state_file = state_file or state_file_path(OASKD_SPEC.state_file_name)
    return askd_rpc.shutdown_daemon("oask", timeout_s, state_file)
