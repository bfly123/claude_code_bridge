from __future__ import annotations

from typing import Any

from .common import ensure_session_health


def send_message(comm, content: str) -> tuple[str, dict[str, Any]]:
    marker = comm._generate_marker()
    comm._send_via_terminal(content)
    state = comm.log_reader.capture_state()
    return marker, state


def ask_async(comm, question: str) -> bool:
    try:
        ensure_session_health(comm)
        comm._send_via_terminal(question)
        print("✅ Sent to Gemini")
        print("Hint: use `ccb pend <agent|job_id>` for control-plane reply inspection")
        return True
    except Exception as exc:
        print(f"❌ Send failed: {exc}")
        return False


__all__ = ["ask_async", "send_message"]
