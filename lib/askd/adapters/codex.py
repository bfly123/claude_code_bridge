"""
Codex provider adapter for the unified ask daemon.

Wraps existing caskd_* modules to provide a consistent interface.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Optional

from askd.adapters.base import BaseProviderAdapter, ProviderRequest, ProviderResult, QueuedTask
from askd_runtime import log_path, write_log
from ccb_protocol import REQ_ID_PREFIX, is_done_text, strip_done_text, extract_reply_for_req, wrap_codex_prompt
from caskd_session import CodexProjectSession, compute_session_key, load_project_session
from codex_comm import CodexCommunicator, CodexLogReader
from completion_hook import (
    COMPLETION_STATUS_CANCELLED,
    COMPLETION_STATUS_COMPLETED,
    COMPLETION_STATUS_FAILED,
    COMPLETION_STATUS_INCOMPLETE,
    default_reply_for_status,
    notify_completion,
)
from providers import CASKD_SPEC
from terminal import get_backend_for_session, is_windows


def _now_ms() -> int:
    return int(time.time() * 1000)


def _write_log(line: str) -> None:
    write_log(log_path(CASKD_SPEC.log_file_name), line)


def _tail_state_for_log(log_path_val: Optional[Path], *, tail_bytes: int) -> dict:
    if not log_path_val:
        return {"log_path": None, "offset": 0}
    try:
        size = log_path_val.stat().st_size
    except OSError:
        size = 0
    offset = max(0, int(size) - int(tail_bytes))
    return {"log_path": log_path_val, "offset": offset}


def _scan_latest_any_log(work_dir: Path) -> Optional[Path]:
    try:
        return CodexLogReader(log_path=None, session_id_filter=None, work_dir=work_dir).current_log_path()
    except Exception:
        return None


def _is_log_stale(preferred: Optional[Path], latest: Optional[Path], threshold_s: float) -> bool:
    if not latest:
        return False
    if not preferred or not preferred.exists():
        return True
    if threshold_s <= 0:
        return False
    try:
        preferred_mtime = preferred.stat().st_mtime
        latest_mtime = latest.stat().st_mtime
    except OSError:
        return True
    return latest_mtime - preferred_mtime >= threshold_s


class CodexAdapter(BaseProviderAdapter):
    """Adapter for Codex (WezTerm) provider."""

    @property
    def key(self) -> str:
        return "codex"

    @property
    def spec(self):
        return CASKD_SPEC

    @property
    def session_filename(self) -> str:
        return ".codex-session"

    def load_session(self, work_dir: Path, instance: Optional[str] = None) -> Optional[CodexProjectSession]:
        return load_project_session(work_dir, instance)

    def compute_session_key(self, session: Any, instance: Optional[str] = None) -> str:
        return compute_session_key(session, instance) if session else "codex:unknown"

    def handle_task(self, task: QueuedTask) -> ProviderResult:
        started_ms = _now_ms()
        started_at = time.time()
        req = task.request
        work_dir = Path(req.work_dir)
        _write_log(f"[INFO] start provider=codex req_id={task.req_id} work_dir={req.work_dir} caller={req.caller}")

        instance = task.request.instance
        session = load_project_session(work_dir, instance)
        session_key = self.compute_session_key(session, instance)

        if not session:
            return ProviderResult(
                exit_code=1,
                reply="No active Codex session found for work_dir.",
                req_id=task.req_id,
                session_key=session_key,
                done_seen=False,
                status=COMPLETION_STATUS_FAILED,
            )

        ok, pane_or_err = session.ensure_pane()
        if not ok:
            return ProviderResult(
                exit_code=1,
                reply=f"Session pane not available: {pane_or_err}",
                req_id=task.req_id,
                session_key=session_key,
                done_seen=False,
                status=COMPLETION_STATUS_FAILED,
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
                status=COMPLETION_STATUS_FAILED,
            )

        prompt = wrap_codex_prompt(req.message, task.req_id)
        preferred_log = session.codex_session_path or None
        codex_session_id = session.codex_session_id or None
        reader = CodexLogReader(
            log_path=preferred_log,
            session_id_filter=codex_session_id,
            work_dir=Path(session.work_dir),
        )
        state = reader.capture_state()
        backend.send_text(pane_id, prompt)

        deadline = None if float(req.timeout_s) < 0.0 else (time.time() + float(req.timeout_s))
        chunks: list[str] = []
        anchor_seen = False
        done_seen = False
        anchor_ms: Optional[int] = None
        done_ms: Optional[int] = None
        fallback_scan = False

        # Idle timeout detection for degraded completion
        idle_timeout = float(os.environ.get("CCB_CASKD_IDLE_TIMEOUT", "8.0"))
        _last_reply_snapshot = ""
        _last_reply_changed_at = time.time()

        anchor_collect_grace = min(deadline, time.time() + 2.0) if deadline else (time.time() + 2.0)
        last_pane_check = time.time()
        default_interval = "5.0" if is_windows() else "2.0"
        pane_check_interval = float(os.environ.get("CCB_CASKD_PANE_CHECK_INTERVAL", default_interval))
        stale_grace_s = float(os.environ.get("CCB_CASKD_STALE_LOG_GRACE_SECONDS", "2.5"))
        stale_check_interval = float(os.environ.get("CCB_CASKD_STALE_LOG_CHECK_INTERVAL", "1.0"))
        stale_threshold_s = float(os.environ.get("CCB_CODEX_STALE_LOG_SECONDS", "10.0"))
        last_stale_check = time.time()

        while True:
            # Check for cancellation
            if task.cancel_event and task.cancel_event.is_set():
                _write_log(f"[INFO] Task cancelled during wait loop: req_id={task.req_id}")
                break

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
                    _write_log(f"[ERROR] Pane {pane_id} died during request req_id={task.req_id}")
                    codex_log_path = None
                    try:
                        lp = reader.current_log_path()
                        if lp:
                            codex_log_path = str(lp)
                    except Exception:
                        pass
                    return ProviderResult(
                        exit_code=1,
                        reply="Codex pane died during request",
                        req_id=task.req_id,
                        session_key=session_key,
                        done_seen=False,
                        anchor_seen=anchor_seen,
                        fallback_scan=fallback_scan,
                        anchor_ms=anchor_ms,
                        log_path=codex_log_path,
                        status=COMPLETION_STATUS_FAILED,
                    )
                last_pane_check = time.time()

            event, state = reader.wait_for_event(state, wait_step)

            if event is None:
                # Stale log detection: if no anchor and no chunks yet,
                # check whether a newer session log appeared (e.g. after pane restart).
                if (not anchor_seen) and (not chunks):
                    now = time.time()
                    if now - started_at >= stale_grace_s and now - last_stale_check >= stale_check_interval:
                        last_stale_check = now
                        latest_log = _scan_latest_any_log(Path(session.work_dir))
                        current_log = state.get("log_path")
                        if isinstance(current_log, str):
                            current_log = Path(current_log)
                        if latest_log and latest_log != current_log and _is_log_stale(current_log, latest_log, stale_threshold_s):
                            reader = CodexLogReader(
                                log_path=latest_log,
                                session_id_filter=None,
                                work_dir=Path(session.work_dir),
                            )
                            state = reader.capture_state()
                            fallback_scan = True
                            try:
                                new_session_id = CodexCommunicator._extract_session_id(latest_log)
                            except Exception:
                                new_session_id = None
                            try:
                                session.update_codex_log_binding(
                                    log_path=str(latest_log),
                                    session_id=new_session_id,
                                )
                            except Exception:
                                pass
                            preferred_log = str(latest_log)
                            codex_session_id = new_session_id or None
                            _write_log(f"[WARN] stale codex log detected; switching to {latest_log}")
                continue

            role, text = event
            if role == "user":
                if f"{REQ_ID_PREFIX} {task.req_id}" in text:
                    anchor_seen = True
                    if anchor_ms is None:
                        anchor_ms = _now_ms() - started_ms
                continue

            if role != "assistant":
                continue

            # Use grace window: allow collecting after grace period even without anchor
            # (but prefer waiting for anchor during grace period)
            if (not anchor_seen) and time.time() < anchor_collect_grace:
                continue

            chunks.append(text)
            combined = "\n".join(chunks)
            if is_done_text(combined, task.req_id):
                done_seen = True
                done_ms = _now_ms() - started_ms
                break

            # Idle-timeout: detect when Codex finished but forgot CCB_DONE
            if combined != _last_reply_snapshot:
                _last_reply_snapshot = combined
                _last_reply_changed_at = time.time()
            elif combined and (time.time() - _last_reply_changed_at >= idle_timeout):
                _write_log(
                    f"[WARN] Codex reply idle for {idle_timeout}s without CCB_DONE, "
                    f"accepting as complete req_id={task.req_id}"
                )
                done_seen = True
                done_ms = _now_ms() - started_ms
                break

        combined = "\n".join(chunks)
        reply = extract_reply_for_req(combined, task.req_id)
        status = COMPLETION_STATUS_COMPLETED if done_seen else COMPLETION_STATUS_INCOMPLETE
        if task.cancelled:
            status = COMPLETION_STATUS_CANCELLED

        codex_log_path = None
        try:
            lp = state.get("log_path")
            if lp:
                codex_log_path = str(lp)
        except Exception:
            pass

        result = ProviderResult(
            exit_code=0 if done_seen else 2,
            reply=reply,
            req_id=task.req_id,
            session_key=session_key,
            done_seen=done_seen,
            done_ms=done_ms,
            anchor_seen=anchor_seen,
            anchor_ms=anchor_ms,
            fallback_scan=fallback_scan,
            log_path=codex_log_path,
            status=status,
        )
        _write_log(
            f"[INFO] done provider=codex req_id={task.req_id} exit={result.exit_code} "
            f"anchor={result.anchor_seen} done={result.done_seen}"
        )

        reply_for_hook = reply
        if not reply_for_hook.strip():
            reply_for_hook = default_reply_for_status(status, done_seen=done_seen)
        _write_log(f"[INFO] notify_completion caller={req.caller} status={status} done_seen={done_seen}")
        notify_completion(
            provider="codex",
            output_file=req.output_path,
            reply=reply_for_hook,
            req_id=task.req_id,
            done_seen=done_seen,
            status=status,
            caller=req.caller,
            email_req_id=req.email_req_id,
            email_msg_id=req.email_msg_id,
            email_from=req.email_from,
            work_dir=req.work_dir,
            caller_pane_id=req.caller_pane_id,
            caller_terminal=req.caller_terminal,
        )

        return result
