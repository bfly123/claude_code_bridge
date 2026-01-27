"""
Droid provider adapter for the unified ask daemon.

Wraps existing daskd_* modules to provide a consistent interface.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Optional

from askd.adapters.base import BaseProviderAdapter, ProviderRequest, ProviderResult, QueuedTask
from askd_runtime import log_path, write_log
from ccb_protocol import REQ_ID_PREFIX
from completion_hook import notify_completion
from daskd_protocol import extract_reply_for_req, is_done_text, wrap_droid_prompt
from daskd_session import compute_session_key, load_project_session
from droid_comm import DroidLogReader
from providers import DASKD_SPEC
from terminal import get_backend_for_session


def _now_ms() -> int:
    return int(time.time() * 1000)


def _write_log(line: str) -> None:
    write_log(log_path(DASKD_SPEC.log_file_name), line)


def _tail_state_for_log(log_path_val: Optional[Path], *, tail_bytes: int) -> dict:
    if not log_path_val or not log_path_val.exists():
        return {"session_path": log_path_val, "offset": 0, "carry": b""}
    try:
        size = log_path_val.stat().st_size
    except OSError:
        size = 0
    offset = max(0, size - max(0, int(tail_bytes)))
    return {"session_path": log_path_val, "offset": offset, "carry": b""}


class DroidAdapter(BaseProviderAdapter):
    """Adapter for Droid provider."""

    @property
    def key(self) -> str:
        return "droid"

    @property
    def spec(self):
        return DASKD_SPEC

    @property
    def session_filename(self) -> str:
        return ".droid-session"

    def load_session(self, work_dir: Path) -> Optional[Any]:
        return load_project_session(work_dir)

    def compute_session_key(self, session: Any) -> str:
        return compute_session_key(session) if session else "droid:unknown"

    def handle_task(self, task: QueuedTask) -> ProviderResult:
        started_ms = _now_ms()
        req = task.request
        work_dir = Path(req.work_dir)
        _write_log(f"[INFO] start provider=droid req_id={task.req_id} work_dir={req.work_dir}")

        session = load_project_session(work_dir)
        session_key = self.compute_session_key(session)

        if not session:
            return ProviderResult(
                exit_code=1,
                reply="No active Droid session found for work_dir.",
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

        log_reader = DroidLogReader(work_dir=Path(session.work_dir))
        if session.droid_session_path:
            try:
                log_reader.set_preferred_session(Path(session.droid_session_path))
            except Exception:
                pass
        if session.droid_session_id:
            log_reader.set_session_id_hint(session.droid_session_id)
        state = log_reader.capture_state()

        prompt = wrap_droid_prompt(req.message, task.req_id)
        backend.send_text(pane_id, prompt)

        deadline = None if float(req.timeout_s) < 0.0 else (time.time() + float(req.timeout_s))
        chunks: list[str] = []
        anchor_seen = False
        fallback_scan = False
        anchor_ms: Optional[int] = None
        done_seen = False
        done_ms: Optional[int] = None

        anchor_grace_deadline = min(deadline, time.time() + 1.5) if deadline else (time.time() + 1.5)
        anchor_collect_grace = min(deadline, time.time() + 2.0) if deadline else (time.time() + 2.0)
        rebounded = False
        tail_bytes = int(os.environ.get("CCB_DASKD_REBIND_TAIL_BYTES", str(2 * 1024 * 1024)))
        pane_check_interval = float(os.environ.get("CCB_DASKD_PANE_CHECK_INTERVAL", "2.0"))
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
                    _write_log(f"[ERROR] Pane {pane_id} died during request req_id={task.req_id}")
                    return ProviderResult(
                        exit_code=1,
                        reply="Droid pane died during request",
                        req_id=task.req_id,
                        session_key=session_key,
                        done_seen=False,
                        anchor_seen=anchor_seen,
                        fallback_scan=fallback_scan,
                        anchor_ms=anchor_ms,
                    )
                last_pane_check = time.time()

            events, state = log_reader.wait_for_events(state, wait_step)
            if not events:
                if (not rebounded) and (not anchor_seen) and time.time() >= anchor_grace_deadline:
                    log_reader = DroidLogReader(work_dir=Path(session.work_dir))
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
        final_reply = extract_reply_for_req(combined, task.req_id)

        notify_completion(
            provider="droid",
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
            anchor_seen=anchor_seen,
            anchor_ms=anchor_ms,
            fallback_scan=fallback_scan,
        )
        _write_log(f"[INFO] done provider=droid req_id={task.req_id} exit={result.exit_code}")
        return result
