"""
Gemini provider adapter for the unified ask daemon.

Wraps existing gaskd_* modules to provide a consistent interface.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from askd.adapters.base import BaseProviderAdapter, ProviderRequest, ProviderResult, QueuedTask
from askd_runtime import log_path, write_log
from completion_hook import notify_completion
from gaskd_protocol import extract_reply_for_req, is_done_text, wrap_gemini_prompt
from gaskd_session import compute_session_key, load_project_session
from gemini_comm import GeminiLogReader
from providers import GASKD_SPEC
from terminal import get_backend_for_session


def _now_ms() -> int:
    return int(time.time() * 1000)


def _write_log(line: str) -> None:
    write_log(log_path(GASKD_SPEC.log_file_name), line)


def _is_cancel_text(text: str) -> bool:
    s = (text or "").strip().lower()
    if not s:
        return False
    if "request cancelled" in s or "request canceled" in s:
        return True
    return False


def _read_session_messages(session_path: Path) -> Optional[list[dict]]:
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
        except Exception:
            return None


def _cancel_applies_to_req(messages: list[dict], cancel_index: int, req_id: str) -> bool:
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


class GeminiAdapter(BaseProviderAdapter):
    """Adapter for Gemini provider."""

    @property
    def key(self) -> str:
        return "gemini"

    @property
    def spec(self):
        return GASKD_SPEC

    @property
    def session_filename(self) -> str:
        return ".gemini-session"

    def load_session(self, work_dir: Path) -> Optional[Any]:
        return load_project_session(work_dir)

    def compute_session_key(self, session: Any) -> str:
        return compute_session_key(session) if session else "gemini:unknown"

    def handle_task(self, task: QueuedTask) -> ProviderResult:
        started_ms = _now_ms()
        req = task.request
        work_dir = Path(req.work_dir)
        _write_log(f"[INFO] start provider=gemini req_id={task.req_id} work_dir={req.work_dir}")

        session = load_project_session(work_dir)
        session_key = self.compute_session_key(session)

        if not session:
            return ProviderResult(
                exit_code=1,
                reply="No active Gemini session found for work_dir.",
                req_id=task.req_id,
                session_key=session_key,
                done_seen=False,
            )

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

        log_reader = GeminiLogReader(work_dir=Path(session.work_dir))
        if session.gemini_session_path:
            try:
                log_reader.set_preferred_session(Path(session.gemini_session_path))
            except Exception:
                pass
        state = log_reader.capture_state()

        prompt = wrap_gemini_prompt(req.message, task.req_id)
        backend.send_text(pane_id, prompt)

        deadline = None if float(req.timeout_s) < 0.0 else (time.time() + float(req.timeout_s))
        done_seen = False
        done_ms: Optional[int] = None
        latest_reply = ""

        pane_check_interval = float(os.environ.get("CCB_GASKD_PANE_CHECK_INTERVAL", "2.0"))
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
                        reply="Gemini pane died during request",
                        req_id=task.req_id,
                        session_key=session_key,
                        done_seen=False,
                    )
                last_pane_check = time.time()

            scan_from = state.get("msg_count")
            try:
                scan_from_i = int(scan_from) if scan_from is not None else 0
            except Exception:
                scan_from_i = 0

            prev_session_path = state.get("session_path")
            reply, state = log_reader.wait_for_message(state, wait_step)

            # Detect cancellation
            try:
                current_count = int(state.get("msg_count") or 0)
            except Exception:
                current_count = 0
            session_path = state.get("session_path")
            if isinstance(session_path, Path) and isinstance(prev_session_path, Path):
                if session_path != prev_session_path:
                    scan_from_i = 0
            if isinstance(session_path, Path) and current_count > scan_from_i:
                if _detect_request_cancelled(session_path, from_index=scan_from_i, req_id=task.req_id):
                    _write_log(f"[WARN] Gemini request cancelled req_id={task.req_id}")
                    return ProviderResult(
                        exit_code=1,
                        reply="Gemini request cancelled.",
                        req_id=task.req_id,
                        session_key=session_key,
                        done_seen=False,
                    )

            if not reply:
                continue
            latest_reply = str(reply)
            if is_done_text(latest_reply, task.req_id):
                done_seen = True
                done_ms = _now_ms() - started_ms
                break

        final_reply = extract_reply_for_req(latest_reply, task.req_id)

        # Fallback: if timeout but we have a reply with any CCB_DONE marker,
        # accept it even if req_id doesn't match (degraded completion detection)
        if not done_seen and latest_reply and "CCB_DONE:" in latest_reply:
            _write_log(f"[WARN] Found CCB_DONE but req_id mismatch for req_id={task.req_id}")
            # Extract the mismatched req_id for logging
            for line in latest_reply.splitlines():
                if "CCB_DONE:" in line:
                    _write_log(f"[WARN] Expected: CCB_DONE: {task.req_id}, Found: {line.strip()}")
                    break
            # Accept as completed in degraded mode
            done_seen = True
            done_ms = _now_ms() - started_ms

        notify_completion(
            provider="gemini",
            output_file=req.output_path,
            reply=final_reply,
            req_id=task.req_id,
            done_seen=done_seen,
            caller=req.caller,
            email_req_id=req.email_req_id,
            email_msg_id=req.email_msg_id,
            email_from=req.email_from,
            work_dir=req.work_dir,
        )

        result = ProviderResult(
            exit_code=0 if done_seen else 2,
            reply=final_reply,
            req_id=task.req_id,
            session_key=session_key,
            done_seen=done_seen,
            done_ms=done_ms,
        )
        _write_log(f"[INFO] done provider=gemini req_id={task.req_id} exit={result.exit_code}")
        return result
