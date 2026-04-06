from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .common import ensure_session_health, remember_log_hint


def send_message(comm, content: str) -> tuple[str, dict[str, Any]]:
    marker = comm._generate_marker()
    message = {
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "marker": marker,
    }

    state = comm.log_reader.capture_state()
    with open(comm.input_fifo, "w", encoding="utf-8") as fifo:
        fifo.write(json.dumps(message, ensure_ascii=False) + "\n")
        fifo.flush()
    return marker, state


def ask_async(comm, question: str) -> bool:
    try:
        ensure_session_health(comm)
        marker, state = comm._send_message(question)
        remember_log_hint(comm, state)
        print(f"✅ Sent to Codex (marker: {marker[:12]}...)")
        print("Tip: use `ccb pend <agent|job_id>` for control-plane reply inspection")
        return True
    except Exception as exc:
        print(f"❌ Send failed: {exc}")
        return False


__all__ = ["ask_async", "send_message"]
