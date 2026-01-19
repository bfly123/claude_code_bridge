from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from worker_pool import BaseSessionWorker, PerSessionWorkerPool

from gaskd_protocol import (
    GaskdRequest,
    GaskdResult,
    extract_reply_for_req,
    is_done_text,
    make_req_id,
    wrap_gemini_prompt,
)
from gaskd_session import compute_session_key, load_project_session
from gemini_comm import GeminiLogReader
from pane_registry import upsert_registry
from project_id import compute_ccb_project_id
from terminal import get_backend_for_session
from askd_runtime import state_file_path, log_path, write_log, random_token
import askd_rpc
from askd_server import AskDaemonServer
from providers import GASKD_SPEC


def _now_ms() -> int:
    return int(time.time() * 1000)


def _write_log(line: str) -> None:
    write_log(log_path(GASKD_SPEC.log_file_name), line)


def _is_cancel_text(text: str) -> bool:
    s = (text or "").strip().lower()
    if not s:
        return False
    # Observed in Gemini session JSON: {"type":"info","content":"Request cancelled."}
    if "request cancelled" in s or "request canceled" in s:
        return True
    return False


def _read_session_messages(session_path: Path) -> Optional[list[dict]]:
    # Gemini session JSON may be written in-place; retry briefly on JSONDecodeError.
    for attempt in range(10):
        try:
            with session_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            messages = data.get("messages", []) if isinstance(data, dict) else []
            return messages if isinstance(messages, list) else []
        except json.JSONDecodeError:
            if attempt < 9:
                time.sleep(0.05)
                continue
            return None
        except OSError:
            return None
        except Exception:
            return None


def _cancel_applies_to_req(messages: list[dict], cancel_index: int, req_id: str) -> bool:
    # The info message itself doesn't include req_id; match it to the nearest preceding user prompt.
    needle = f"CCB_REQ_ID: {req_id}"
    for j in range(cancel_index - 1, -1, -1):
        msg = messages[j]
        if not isinstance(msg, dict):
            continue
        if msg.get("type") != "user":
            continue
        content = msg.get("content")
        if not isinstance(content, str):
            content = str(content or "")
        return needle in content
    return False


def _detect_request_cancelled(session_path: Path, *, from_index: int, req_id: str) -> bool:
    if from_index < 0:
        from_index = 0
    messages = _read_session_messages(session_path)
    if messages is None:
        return False
    for i in range(min(from_index, len(messages)), len(messages)):
        msg = messages[i]
        if not isinstance(msg, dict):
            continue
        if msg.get("type") != "info":
            continue
        content = msg.get("content")
        if not isinstance(content, str):
            content = str(content or "")
        if not _is_cancel_text(content):
            continue
        if _cancel_applies_to_req(messages, i, req_id):
            return True
    return False


def _read_gemini_session_id(session_path: Path) -> str:
    if not session_path or not session_path.exists():
        return ""
    # Gemini CLI may write in-place; retry briefly on JSONDecodeError.
    for attempt in range(10):
        try:
            with session_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict) and isinstance(payload.get("sessionId"), str):
                return payload["sessionId"]
            return ""
        except json.JSONDecodeError:
            if attempt < 9:
                time.sleep(0.05)
                continue
            return ""
        except Exception:
            return ""


@dataclass
class _QueuedTask:
    request: GaskdRequest
    created_ms: int
    req_id: str
    done_event: threading.Event
    result: Optional[GaskdResult] = None


class _SessionWorker(BaseSessionWorker[_QueuedTask, GaskdResult]):
    def _handle_exception(self, exc: Exception, task: _QueuedTask) -> GaskdResult:
        _write_log(f"[ERROR] session={self.session_key} req_id={task.req_id} {exc}")
        return GaskdResult(
            exit_code=1,
            reply=str(exc),
            req_id=task.req_id,
            session_key=self.session_key,
            done_seen=False,
            done_ms=None,
        )

    def _handle_task(self, task: _QueuedTask) -> GaskdResult:
        started_ms = _now_ms()
        req = task.request
        work_dir = Path(req.work_dir)
        _write_log(f"[INFO] start session={self.session_key} req_id={task.req_id} work_dir={req.work_dir}")

        session = load_project_session(work_dir)
        if not session:
            return GaskdResult(
                exit_code=1,
                reply="❌ No active Gemini session found for work_dir. Run 'ccb gemini' (or add gemini to ccb.config) in that project first.",
                req_id=task.req_id,
                session_key=self.session_key,
                done_seen=False,
                done_ms=None,
            )

        ok, pane_or_err = session.ensure_pane()
        if not ok:
            return GaskdResult(
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
            return GaskdResult(
                exit_code=1,
                reply="❌ Terminal backend not available",
                req_id=task.req_id,
                session_key=self.session_key,
                done_seen=False,
                done_ms=None,
            )

        log_reader = GeminiLogReader(work_dir=Path(session.work_dir))
        if session.gemini_session_path:
            try:
                log_reader.set_preferred_session(Path(session.gemini_session_path))
            except Exception:
                pass
        state = log_reader.capture_state()

        # Best-effort: persist the latest binding so other processes (gpend, registry routing, etc.)
        # can follow session rotations ("new") without manual intervention.
        try:
            session_path = state.get("session_path")
            session_id = _read_gemini_session_id(session_path) if isinstance(session_path, Path) else ""
            session.update_gemini_binding(session_path=session_path if isinstance(session_path, Path) else None, session_id=session_id or None)
            ccb_pid = str(session.data.get("ccb_project_id") or "").strip()
            if not ccb_pid:
                ccb_pid = compute_ccb_project_id(Path(session.work_dir))
            ccb_session_id = str(session.data.get("ccb_session_id") or session.data.get("session_id") or "").strip()
            if ccb_session_id:
                upsert_registry(
                    {
                        "ccb_session_id": ccb_session_id,
                        "ccb_project_id": ccb_pid or None,
                        "work_dir": str(session.work_dir),
                        "terminal": session.terminal,
                        "providers": {
                            "gemini": {
                                "pane_id": session.pane_id or None,
                                "pane_title_marker": session.pane_title_marker or None,
                                "session_file": str(session.session_file),
                                "gemini_session_id": session.data.get("gemini_session_id"),
                                "gemini_session_path": session.data.get("gemini_session_path"),
                            }
                        },
                    }
                )
        except Exception:
            pass

        prompt = wrap_gemini_prompt(req.message, task.req_id)
        backend.send_text(pane_id, prompt)

        deadline = None if float(req.timeout_s) < 0.0 else (time.time() + float(req.timeout_s))
        done_seen = False
        done_ms: int | None = None
        latest_reply = ""

        pane_check_interval = float(os.environ.get("CCB_GASKD_PANE_CHECK_INTERVAL", "2.0") or "2.0")
        last_pane_check = time.time()

        while True:
            if deadline is not None:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                wait_step = min(remaining, 1.0)
            else:
                wait_step = 1.0

            if time.time() - last_pane_check >= pane_check_interval:
                try:
                    alive = bool(backend.is_alive(pane_id))
                except Exception:
                    alive = False
                if not alive:
                    _write_log(f"[ERROR] Pane {pane_id} died during request session={self.session_key} req_id={task.req_id}")
                    return GaskdResult(
                        exit_code=1,
                        reply="❌ Gemini pane died during request",
                        req_id=task.req_id,
                        session_key=self.session_key,
                        done_seen=False,
                        done_ms=None,
                    )
                last_pane_check = time.time()

            scan_from = state.get("msg_count")
            try:
                scan_from_i = int(scan_from) if scan_from is not None else 0
            except Exception:
                scan_from_i = 0

            prev_session_path = state.get("session_path")
            reply, state = log_reader.wait_for_message(state, wait_step)

            # Detect user cancellation via Gemini session JSON info message.
            try:
                current_count = int(state.get("msg_count") or 0)
            except Exception:
                current_count = 0
            session_path = state.get("session_path")
            if isinstance(session_path, Path) and isinstance(prev_session_path, Path) and session_path != prev_session_path:
                scan_from_i = 0
            if isinstance(session_path, Path) and current_count > scan_from_i:
                if _detect_request_cancelled(session_path, from_index=scan_from_i, req_id=task.req_id):
                    _write_log(f"[WARN] Gemini request cancelled - skipping task session={self.session_key} req_id={task.req_id}")
                    return GaskdResult(
                        exit_code=1,
                        reply="❌ Gemini request cancelled. Skipping to next task.",
                        req_id=task.req_id,
                        session_key=self.session_key,
                        done_seen=False,
                        done_ms=None,
                    )

            if not reply:
                continue
            latest_reply = str(reply)
            if is_done_text(latest_reply, task.req_id):
                done_seen = True
                done_ms = _now_ms() - started_ms
                break

        final_reply = extract_reply_for_req(latest_reply, task.req_id)
        return GaskdResult(
            exit_code=0 if done_seen else 2,
            reply=final_reply,
            req_id=task.req_id,
            session_key=self.session_key,
            done_seen=done_seen,
            done_ms=done_ms,
        )


class _WorkerPool:
    def __init__(self):
        self._pool = PerSessionWorkerPool[_SessionWorker]()

    def submit(self, request: GaskdRequest) -> _QueuedTask:
        req_id = make_req_id()
        task = _QueuedTask(request=request, created_ms=_now_ms(), req_id=req_id, done_event=threading.Event())

        session = load_project_session(Path(request.work_dir))
        session_key = compute_session_key(session) if session else "gemini:unknown"

        worker = self._pool.get_or_create(session_key, _SessionWorker)
        worker.enqueue(task)
        return task


class GaskdServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0, *, state_file: Optional[Path] = None):
        self.host = host
        self.port = port
        self.state_file = state_file or state_file_path(GASKD_SPEC.state_file_name)
        self.token = random_token()
        self.pool = _WorkerPool()

    def serve_forever(self) -> int:
        def _handle_request(msg: dict) -> dict:
            try:
                req = GaskdRequest(
                    client_id=str(msg.get("id") or ""),
                    work_dir=str(msg.get("work_dir") or ""),
                    timeout_s=float(msg.get("timeout_s") or 300.0),
                    quiet=bool(msg.get("quiet") or False),
                    message=str(msg.get("message") or ""),
                    output_path=str(msg.get("output_path")) if msg.get("output_path") else None,
                )
            except Exception as exc:
                return {"type": "gask.response", "v": 1, "id": msg.get("id"), "exit_code": 1, "reply": f"Bad request: {exc}"}

            task = self.pool.submit(req)
            wait_timeout = None if float(req.timeout_s) < 0.0 else (float(req.timeout_s) + 5.0)
            task.done_event.wait(timeout=wait_timeout)
            result = task.result
            if not result:
                return {"type": "gask.response", "v": 1, "id": req.client_id, "exit_code": 2, "reply": ""}

            return {
                "type": "gask.response",
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
            spec=GASKD_SPEC,
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
    state_file = state_file or state_file_path(GASKD_SPEC.state_file_name)
    return askd_rpc.read_state(state_file)


def ping_daemon(timeout_s: float = 0.5, state_file: Optional[Path] = None) -> bool:
    state_file = state_file or state_file_path(GASKD_SPEC.state_file_name)
    return askd_rpc.ping_daemon("gask", timeout_s, state_file)


def shutdown_daemon(timeout_s: float = 1.0, state_file: Optional[Path] = None) -> bool:
    state_file = state_file or state_file_path(GASKD_SPEC.state_file_name)
    return askd_rpc.shutdown_daemon("gask", timeout_s, state_file)
