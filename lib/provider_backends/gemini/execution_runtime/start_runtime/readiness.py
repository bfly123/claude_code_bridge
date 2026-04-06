from __future__ import annotations

import os
import time
from dataclasses import dataclass


def looks_ready(text: str) -> bool:
    return 'Type your message' in str(text or '')


def wait_for_runtime_ready(backend: object, pane_id: str, *, timeout_s: float = 20.0) -> None:
    get_pane_content = pane_content_reader(backend)
    if get_pane_content is None:
        return
    deadline = time.time() + resolved_timeout(timeout_s)
    state = ReadinessState()
    while time.time() < deadline:
        text = read_pane_text(get_pane_content, pane_id)
        if text is None:
            return
        note_content(state, text)
        if stable_ready_seen(state, text):
            time.sleep(0.3)
            return
        time.sleep(0.2)
    if state.saw_content:
        return


@dataclass
class ReadinessState:
    stable_text: str = ''
    stable_since: float | None = None
    saw_content: bool = False


def pane_content_reader(backend: object):
    get_pane_content = getattr(backend, 'get_pane_content', None)
    return get_pane_content if callable(get_pane_content) else None


def resolved_timeout(timeout_s: float) -> float:
    try:
        return max(0.0, float(os.environ.get('CCB_GEMINI_READY_TIMEOUT_S', timeout_s)))
    except Exception:
        return max(0.0, timeout_s)


def read_pane_text(get_pane_content, pane_id: str) -> str | None:
    try:
        return str(get_pane_content(pane_id, lines=120) or '')
    except Exception:
        return None


def note_content(state: ReadinessState, text: str) -> None:
    if text.strip():
        state.saw_content = True


def stable_ready_seen(state: ReadinessState, text: str) -> bool:
    if not looks_ready(text):
        reset_stable_state(state)
        return False
    fingerprint = text.strip()
    if fingerprint != state.stable_text:
        state.stable_text = fingerprint
        state.stable_since = time.time()
        return False
    if state.stable_since is None:
        state.stable_since = time.time()
        return False
    return time.time() - state.stable_since >= 1.5


def reset_stable_state(state: ReadinessState) -> None:
    state.stable_text = ''
    state.stable_since = None


__all__ = ['looks_ready', 'wait_for_runtime_ready']
