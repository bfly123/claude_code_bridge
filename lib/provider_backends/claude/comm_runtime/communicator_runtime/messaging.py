from __future__ import annotations

import time


def ask_async(comm, question: str) -> bool:
    try:
        healthy, status = comm._check_session_health_impl(probe_terminal=False)
        if not healthy:
            raise RuntimeError(f"❌ Session error: {status}")
        comm._send_via_terminal(question)
        print("✅ Sent to Claude")
        print("Hint: use `ccb pend <agent|job_id>` for control-plane reply inspection")
        return True
    except Exception as exc:
        print(f"❌ Send failed: {exc}")
        return False


def ask_sync(
    comm,
    question: str,
    timeout: int | None = None,
    *,
    req_id_factory,
    wrap_prompt_fn,
    is_done_text_fn,
    strip_done_text_fn,
) -> str | None:
    try:
        healthy, status = comm._check_session_health_impl(probe_terminal=False)
        if not healthy:
            raise RuntimeError(f"❌ Session error: {status}")

        req_id = req_id_factory()
        prompt = wrap_prompt_fn(question, req_id)
        state = comm.log_reader.capture_state()
        comm._send_via_terminal(prompt)

        wait_timeout = comm.timeout if timeout is None else int(timeout)
        deadline = None if wait_timeout < 0 else (time.time() + wait_timeout)
        latest = ""
        done_seen = False

        while True:
            if deadline is not None:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                wait_step = min(remaining, 1.0)
            else:
                wait_step = 1.0

            reply, state = comm.log_reader.wait_for_message(state, timeout=wait_step)
            if reply is None:
                continue
            latest = str(reply)
            if is_done_text_fn(latest, req_id):
                done_seen = True
                break

        if done_seen:
            session_path = comm.log_reader.current_session_path()
            if session_path:
                comm._remember_claude_session(session_path)
            return strip_done_text_fn(latest, req_id)
        return strip_done_text_fn(latest, req_id) if latest else None
    except Exception as exc:
        print(f"❌ Send failed: {exc}")
        return None


def ping(comm, *, display: bool = True) -> tuple[bool, str]:
    healthy, msg = comm._check_session_health_impl(probe_terminal=True)
    if display:
        print(msg)
    return healthy, msg


__all__ = ["ask_async", "ask_sync", "ping"]
