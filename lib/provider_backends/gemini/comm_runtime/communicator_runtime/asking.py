from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from i18n import t


def send_message(comm, content: str) -> tuple[str, dict[str, Any]]:
    marker = comm._generate_marker()
    comm._send_via_terminal(content)
    state = comm.log_reader.capture_state()
    return marker, state


def ask_async(comm, question: str) -> bool:
    try:
        healthy, status = comm._check_session_health_impl(probe_terminal=False)
        if not healthy:
            raise RuntimeError(f"❌ Session error: {status}")

        comm._send_via_terminal(question)
        print("✅ Sent to Gemini")
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

        print(f"🔔 {t('sending_to', provider='Gemini')}", flush=True)
        _, state = comm._send_message(question)

        wait_timeout = comm.timeout if timeout is None else int(timeout)
        if wait_timeout == 0:
            print(f"⏳ {t('waiting_for_reply', provider='Gemini')}", flush=True)
            start_time = time.time()
            last_hint = 0
            while True:
                message, new_state = comm.log_reader.wait_for_message(state, timeout=30.0)
                state = new_state if new_state else state
                session_path = (new_state or {}).get("session_path") if isinstance(new_state, dict) else None
                if isinstance(session_path, Path):
                    comm._remember_gemini_session(session_path)
                if message:
                    print(f"🤖 {t('reply_from', provider='Gemini')}")
                    print(message)
                    return message
                elapsed = int(time.time() - start_time)
                if elapsed >= last_hint + 30:
                    last_hint = elapsed
                    print(f"⏳ Still waiting... ({elapsed}s)")

        print(f"⏳ Waiting for Gemini reply (timeout {wait_timeout}s)...")
        message, new_state = comm.log_reader.wait_for_message(state, float(wait_timeout))
        session_path = (new_state or {}).get("session_path") if isinstance(new_state, dict) else None
        if isinstance(session_path, Path):
            comm._remember_gemini_session(session_path)
        if message:
            print(f"🤖 {t('reply_from', provider='Gemini')}")
            print(message)
            return message

        print(f"⏰ {t('timeout_no_reply', provider='Gemini')}")
        return None
    except Exception as exc:
        print(f"❌ Sync ask failed: {exc}")
        return None


def consume_pending(comm, *, display: bool = True, n: int = 1):
    session_path = comm.log_reader.current_session_path()
    if isinstance(session_path, Path):
        comm._remember_gemini_session(session_path)

    if n > 1:
        conversations = comm.log_reader.latest_conversations(n)
        if not conversations:
            if display:
                print(t('no_reply_available', provider='Gemini'))
            return None
        if display:
            for i, (question, reply) in enumerate(conversations):
                if question:
                    print(f"Q: {question}")
                print(f"A: {reply}")
                if i < len(conversations) - 1:
                    print("---")
        return conversations

    message = comm.log_reader.latest_message()
    if not message:
        if display:
            print(t('no_reply_available', provider='Gemini'))
        return None
    if display:
        print(message)
    return message


__all__ = [
    "ask_async",
    "ask_sync",
    "consume_pending",
    "send_message",
]
