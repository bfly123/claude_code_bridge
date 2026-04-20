from __future__ import annotations

import time

from ui_text import t

from .common import ensure_session_health, remember_session_path


def ask_sync(comm, question: str, timeout: int | None = None) -> str | None:
    try:
        ensure_session_health(comm)
        print(f"🔔 {t('sending_to', provider='Gemini')}", flush=True)
        _, state = comm._send_message(question)

        wait_timeout = comm.timeout if timeout is None else int(timeout)
        if wait_timeout == 0:
            print(f"⏳ {t('waiting_for_reply', provider='Gemini')}", flush=True)
            return _wait_indefinitely(comm, state)

        print(f"⏳ Waiting for Gemini reply (timeout {wait_timeout}s)...")
        return _wait_once(comm, state, float(wait_timeout))
    except Exception as exc:
        print(f"❌ Sync ask failed: {exc}")
        return None


def _wait_indefinitely(comm, state) -> str | None:
    start_time = time.time()
    last_hint = 0
    while True:
        message, state = _wait_for_message(comm, state, timeout=30.0)
        if message:
            return _display_reply(message)
        elapsed = int(time.time() - start_time)
        if elapsed >= last_hint + 30:
            last_hint = elapsed
            print(f"⏳ Still waiting... ({elapsed}s)")


def _wait_once(comm, state, timeout: float) -> str | None:
    message, _ = _wait_for_message(comm, state, timeout=timeout)
    if message:
        return _display_reply(message)
    print(f"⏰ {t('timeout_no_reply', provider='Gemini')}")
    return None


def _wait_for_message(comm, state, *, timeout: float):
    message, new_state = comm.log_reader.wait_for_message(state, timeout)
    next_state = new_state if new_state else state
    remember_session_path(comm, new_state if isinstance(new_state, dict) else next_state)
    return message, next_state


def _display_reply(message: str) -> str:
    print(f"🤖 {t('reply_from', provider='Gemini')}")
    print(message)
    return message


__all__ = ["ask_sync"]
