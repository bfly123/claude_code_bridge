from __future__ import annotations

import re

from opencode_runtime.replies import (
    conversations_from_messages,
    extract_req_id_from_text,
    extract_text,
    find_new_assistant_reply_with_state,
    is_aborted_error,
    latest_message_from_messages,
)


def test_extract_text_falls_back_to_reasoning_only_when_requested() -> None:
    parts = [{'type': 'reasoning', 'text': 'thinking'}, {'type': 'text', 'text': ''}]

    assert extract_text(parts) == 'thinking'
    assert extract_text(parts, allow_reasoning_fallback=False) == ''


def test_find_new_assistant_reply_with_state_accepts_completion_marker_without_completed_time() -> None:
    messages = [{'id': 'msg_1', 'role': 'assistant', 'time': {}}]

    reply, state = find_new_assistant_reply_with_state(
        messages,
        {},
        read_parts=lambda message_id: [{'type': 'text', 'text': f'{message_id} CCB_DONE: finished'}],
        completion_marker='CCB_DONE:',
    )

    assert reply == 'msg_1 CCB_DONE: finished'
    assert state == {
        'assistant_count': 1,
        'last_assistant_id': 'msg_1',
        'last_assistant_completed': 0,
        'last_assistant_has_done': True,
    }


def test_find_new_assistant_reply_with_state_suppresses_duplicate_state() -> None:
    messages = [{'id': 'msg_1', 'role': 'assistant', 'time': {'completed': 1}}]
    state = {
        'assistant_count': 1,
        'last_assistant_id': 'msg_1',
        'last_assistant_completed': 1,
        'last_assistant_has_done': False,
    }

    reply, next_state = find_new_assistant_reply_with_state(
        messages,
        state,
        read_parts=lambda message_id: [{'type': 'text', 'text': message_id}],
        completion_marker='CCB_DONE:',
    )

    assert reply is None
    assert next_state is None


def test_latest_message_from_messages_requires_completed_assistant() -> None:
    messages = [
        {'id': 'u1', 'role': 'user'},
        {'id': 'a1', 'role': 'assistant', 'time': {'completed': 1}},
        {'id': 'a2', 'role': 'assistant', 'time': {}},
    ]
    parts = {
        'a1': [{'type': 'text', 'text': 'done'}],
        'a2': [{'type': 'text', 'text': 'still running'}],
    }

    assert latest_message_from_messages(messages[:-1], read_parts=lambda message_id: parts[message_id]) == 'done'
    assert latest_message_from_messages(messages, read_parts=lambda message_id: parts[message_id]) is None


def test_conversations_from_messages_pairs_user_and_assistant_messages() -> None:
    messages = [
        {'id': 'u1', 'role': 'user'},
        {'id': 'a1', 'role': 'assistant'},
        {'id': 'u2', 'role': 'user'},
        {'id': 'a2', 'role': 'assistant'},
    ]
    parts = {
        'u1': [{'type': 'text', 'text': 'question one'}],
        'a1': [{'type': 'text', 'text': 'answer one'}],
        'u2': [{'type': 'text', 'text': 'question two'}],
        'a2': [{'type': 'text', 'text': 'answer two'}],
    }

    assert conversations_from_messages(messages, read_parts=lambda message_id: parts[message_id], n=1) == [('question two', 'answer two')]
    assert conversations_from_messages(messages, read_parts=lambda message_id: parts[message_id], n=0) == [
        ('question one', 'answer one'),
        ('question two', 'answer two'),
    ]


def test_is_aborted_error_and_extract_req_id_helpers() -> None:
    error = {'data': {'message': 'Request aborted by user'}}

    assert is_aborted_error(error) is True
    assert extract_req_id_from_text('CCB_REQ_ID: Job_ABC123', re.compile(r'CCB_REQ_ID:\s*([A-Za-z0-9_]+)')) == 'job_abc123'
