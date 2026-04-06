from __future__ import annotations

import os
import time
from typing import Any

from opencode_runtime.replies import find_new_assistant_reply_with_state

from ..storage_reader import get_latest_session, read_messages, read_parts
from .loop import read_since as read_since_impl
from .state import merge_reply_state, refresh_observed_state, reset_state_for_session, session_updated


def find_new_assistant_reply_with_reader_state(
    reader,
    session_id: str,
    state: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None]:
    messages = read_messages(reader, session_id)
    completion_marker = _completion_marker()
    reply, reply_state = find_new_assistant_reply_with_state(
        messages,
        state,
        read_parts=lambda message_id: read_parts(reader, message_id),
        completion_marker=completion_marker,
    )
    if reply_state and reply_state.get('last_assistant_completed') == 0:
        reply_state['last_assistant_completed'] = int(time.time() * 1000)
    return reply, reply_state


def read_since(reader, state: dict[str, Any], timeout: float, block: bool) -> tuple[str | None, dict[str, Any]]:
    return read_since_impl(
        reader,
        state,
        timeout,
        block,
        get_latest_session_fn=get_latest_session,
        find_reply_fn=find_new_assistant_reply_with_reader_state,
        merge_reply_state_fn=merge_reply_state,
        refresh_observed_state_fn=refresh_observed_state,
        reset_state_for_session_fn=reset_state_for_session,
        session_updated_fn=session_updated,
    )


def _completion_marker() -> str:
    marker = (os.environ.get('CCB_EXECUTION_COMPLETE_MARKER') or '[EXECUTION_COMPLETE]').strip()
    return marker or '[EXECUTION_COMPLETE]'


__all__ = ['find_new_assistant_reply_with_reader_state', 'read_since']
