"""
OpenCode provider adapter for the unified ask daemon.

Wraps existing oaskd_* modules to provide a consistent interface.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Optional

from askd.adapters.base import BaseProviderAdapter, ProviderRequest, ProviderResult, QueuedTask
from askd_runtime import log_path, write_log
from completion_hook import notify_completion
from env_utils import env_bool
from oaskd_protocol import is_done_text, strip_done_text, wrap_opencode_prompt
from oaskd_session import load_project_session
from opencode_comm import OpenCodeLogReader
from process_lock import ProviderLock
from project_id import compute_ccb_project_id
from providers import OASKD_SPEC
from terminal import get_backend_for_session


def _now_ms() -> int:
    return int(time.time() * 1000)


def _write_log(line: str) -> None:
    write_log(log_path(OASKD_SPEC.log_file_name), line)


def _cancel_detection_enabled(default: bool = False) -> bool:
    return env_bool("CCB_OASKD_CANCEL_DETECT", default)


class OpenCodeAdapter(BaseProviderAdapter):
    """Adapter for OpenCode provider."""

    @property
    def key(self) -> str:
        return "opencode"

    @property
    def spec(self):
        return OASKD_SPEC

    @property
    def session_filename(self) -> str:
        return ".opencode-session"

    def load_session(self, work_dir: Path) -> Optional[Any]:
        return load_project_session(work_dir)

    def compute_session_key(self, session: Any) -> str:
        if not session:
            return "opencode:unknown"
        ccb_project_id = ""
        try:
            ccb_project_id = str(session.data.get("ccb_project_id") or "").strip()
            if not ccb_project_id:
                ccb_project_id = compute_ccb_project_id(Path(session.work_dir))
        except Exception:
            pass
        return f"opencode:{ccb_project_id}" if ccb_project_id else "opencode:unknown"

    def handle_task(self, task: QueuedTask) -> ProviderResult:
        started_ms = _now_ms()
        req = task.request
        work_dir = Path(req.work_dir)
        _write_log(f"[INFO] start provider=opencode req_id={task.req_id} work_dir={req.work_dir}")

        session = load_project_session(work_dir)
        session_key = self.compute_session_key(session)

        if not session:
            return ProviderResult(
                exit_code=1,
                reply="No active OpenCode session found for work_dir.",
                req_id=task.req_id,
                session_key=session_key,
                done_seen=False,
            )

        # Cross-process serialization lock
        if float(req.timeout_s) < 0.0:
            lock_timeout = 300.0
        else:
            lock_timeout = min(300.0, max(1.0, float(req.timeout_s)))
        lock = ProviderLock("opencode", cwd=f"session:{session_key}", timeout=lock_timeout)
        if not lock.acquire():
            return ProviderResult(
                exit_code=1,
                reply="Another OpenCode request is in progress (session lock timeout).",
                req_id=task.req_id,
                session_key=session_key,
                done_seen=False,
            )

        try:
            return self._handle_task_locked(task, session, session_key, started_ms)
        finally:
            lock.release()

    def _handle_task_locked(self, task: QueuedTask, session: Any, session_key: str, started_ms: int) -> ProviderResult:
        req = task.request

        ok, pane_or_err = session.ensure_pane()
        if not ok:
            return ProviderResult(
                exit_code=1,
                reply=f"Session pane not available: {pane_or_err}",
                req_id=task.req_id,
                session_key=session_key,
                done_seen=False,
            )
        pane_id = pane_or_err

        backend = get_backend_for_session(session.data)
        if not backend:
            return ProviderResult(
                exit_code=1,
                reply="Terminal backend not available",
                req_id=task.req_id,
                session_key=session_key,
                done_seen=False,
            )

        log_reader = OpenCodeLogReader(
            work_dir=Path(session.work_dir),
            project_id="global",
            session_id_filter=session.opencode_session_id_filter,
        )
        state = log_reader.capture_state()

        prompt = wrap_opencode_prompt(req.message, task.req_id)
        backend.send_text(pane_id, prompt)

        # Async mode: timeout_s == 0 means fire-and-forget
        if float(req.timeout_s) == 0.0:
            return ProviderResult(
                exit_code=0,
                reply="",
                req_id=task.req_id,
                session_key=session_key,
                done_seen=True,
                done_ms=_now_ms() - started_ms,
            )

        deadline = None if float(req.timeout_s) < 0.0 else (time.time() + float(req.timeout_s))
        chunks: list[str] = []
        done_seen = False
        done_ms: Optional[int] = None

        pane_check_interval = float(os.environ.get("CCB_OASKD_PANE_CHECK_INTERVAL", "2.0"))
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
                    _write_log(f"[ERROR] Pane {pane_id} died during request req_id={task.req_id}")
                    return ProviderResult(
                        exit_code=1,
                        reply="OpenCode pane died during request",
                        req_id=task.req_id,
                        session_key=session_key,
                        done_seen=False,
                    )
                last_pane_check = time.time()

            reply, state = log_reader.wait_for_message(state, wait_step)
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

        notify_completion(
            provider="opencode",
            output_file=req.output_path,
            reply=final_reply,
            req_id=task.req_id,
            done_seen=done_seen,
            caller=req.caller,
        )

        result = ProviderResult(
            exit_code=0 if done_seen else 2,
            reply=final_reply,
            req_id=task.req_id,
            session_key=session_key,
            done_seen=done_seen,
            done_ms=done_ms,
        )
        _write_log(f"[INFO] done provider=opencode req_id={task.req_id} exit={result.exit_code}")
        return result
