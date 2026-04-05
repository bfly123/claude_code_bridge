from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from i18n import t
from provider_core.runtime_specs import provider_marker_prefix


def initialize_state(
    comm,
    *,
    get_backend_for_session_fn,
    get_pane_id_from_session_fn,
    log_reader_cls,
    publish_registry_fn,
) -> None:
    comm.session_info = comm._load_session_info()
    if not comm.session_info:
        raise RuntimeError("❌ No active OpenCode session found. Run 'ccb opencode' (or add opencode to ccb.config) first")

    comm.ccb_session_id = str(comm.session_info.get("ccb_session_id") or "").strip()
    comm.runtime_dir = Path(comm.session_info["runtime_dir"])
    comm.terminal = comm.session_info.get("terminal", os.environ.get("OPENCODE_TERMINAL", "tmux"))
    comm.pane_id = get_pane_id_from_session_fn(comm.session_info) or ""
    comm.pane_title_marker = comm.session_info.get("pane_title_marker") or ""
    comm.backend = get_backend_for_session_fn(comm.session_info)
    comm.timeout = int(os.environ.get("OPENCODE_SYNC_TIMEOUT", "30"))
    comm.marker_prefix = provider_marker_prefix("opencode")
    comm.project_session_file = comm.session_info.get("_session_file")

    comm.log_reader = log_reader_cls(
        work_dir=Path(comm.session_info.get("work_dir") or Path.cwd()),
        project_id="global",
        session_id_filter=(str(comm.session_info.get("opencode_session_id") or "").strip() or None),
    )

    publish_registry_fn(
        ccb_session_id=comm.ccb_session_id,
        session_info=comm.session_info,
        terminal=comm.terminal,
        pane_id=comm.pane_id or None,
        project_session_file=comm.project_session_file,
    )


def check_session_health(comm, *, probe_terminal: bool, storage_root: Path) -> tuple[bool, str]:
    try:
        if not comm.runtime_dir.exists():
            return False, "Runtime directory not found"
        if not comm.pane_id:
            return False, "Session pane not found"
        if probe_terminal and comm.backend:
            pane_alive = comm.backend.is_alive(comm.pane_id)
            if not pane_alive:
                return False, f"{comm.terminal} session {comm.pane_id} not found"

        if not storage_root.exists():
            return False, f"OpenCode storage not found: {storage_root}"
        return True, "Session OK"
    except Exception as exc:
        return False, f"Check failed: {exc}"


def ping(comm, *, display: bool = True) -> tuple[bool, str]:
    healthy, status = comm._check_session_health()
    msg = f"✅ OpenCode connection OK ({status})" if healthy else f"❌ OpenCode connection error: {status}"
    if display:
        print(msg)
    return healthy, msg


def send_message(comm, content: str) -> tuple[str, dict[str, Any]]:
    marker = comm._generate_marker()
    state = comm.log_reader.capture_state()
    comm._send_via_terminal(content)
    return marker, state


def ask_async(comm, question: str) -> bool:
    try:
        healthy, status = comm._check_session_health_impl(probe_terminal=False)
        if not healthy:
            raise RuntimeError(f"❌ Session error: {status}")
        comm._send_via_terminal(question)
        print("✅ Sent to OpenCode")
        print("Hint: use `ccb pend <agent|job_id>` for control-plane reply inspection")
        return True
    except Exception as exc:
        print(f"❌ Send failed: {exc}")
        return False


def ask_sync(comm, question: str, timeout: int | None = None) -> str | None:
    try:
        healthy, status = comm._check_session_health_impl(probe_terminal=False)
        if not healthy:
            raise RuntimeError(f"❌ Session error: {status}")

        print(f"🔔 {t('sending_to', provider='OpenCode')}", flush=True)
        _, state = comm._send_message(question)
        wait_timeout = comm.timeout if timeout is None else int(timeout)
        print(f"⏳ Waiting for OpenCode reply (timeout {wait_timeout}s)...")
        message, _ = comm.log_reader.wait_for_message(state, float(wait_timeout))
        if message:
            print(f"🤖 {t('reply_from', provider='OpenCode')}")
            print(message)
            return message
        print(f"⏰ {t('timeout_no_reply', provider='OpenCode')}")
        return None
    except Exception as exc:
        print(f"❌ Sync ask failed: {exc}")
        return None


__all__ = ["ask_async", "ask_sync", "check_session_health", "initialize_state", "ping", "send_message"]
