from __future__ import annotations

from provider_backends.codex.comm_runtime.log_entries import extract_entry, extract_event, extract_message, extract_user_message


def test_extract_message_from_response_item_joins_assistant_content() -> None:
    entry = {
        'type': 'response_item',
        'payload': {
            'type': 'message',
            'role': 'assistant',
            'content': [
                {'type': 'output_text', 'text': 'hello'},
                {'type': 'text', 'text': 'world'},
            ],
        },
    }

    assert extract_message(entry) == 'hello\nworld'


def test_extract_user_message_from_response_item_input_text() -> None:
    entry = {
        'type': 'response_item',
        'payload': {
            'type': 'message',
            'role': 'user',
            'content': [
                {'type': 'input_text', 'text': 'first'},
                {'type': 'input_text', 'text': 'second'},
            ],
        },
    }

    assert extract_user_message(entry) == 'first\nsecond'
    assert extract_entry(entry) == {
        'entry_type': 'response_item',
        'payload_type': 'message',
        'timestamp': None,
        'phase': None,
        'turn_id': None,
        'task_id': None,
        'reason': None,
        'last_agent_message': None,
        'entry': entry,
        'role': 'user',
        'text': 'first\nsecond',
    }


def test_extract_entry_handles_system_event_payloads() -> None:
    task_complete = {
        'type': 'event_msg',
        'payload': {
            'type': 'task_complete',
            'last_agent_message': 'done',
            'reason': 'completed',
        },
    }
    turn_aborted = {
        'type': 'event_msg',
        'payload': {
            'type': 'turn_aborted',
            'message': 'stopped',
        },
    }

    assert extract_entry(task_complete)['role'] == 'system'
    assert extract_entry(task_complete)['text'] == 'done'
    assert extract_entry(turn_aborted)['reason'] == 'turn_aborted'


def test_extract_event_returns_only_user_or_assistant_messages() -> None:
    entry = {
        'type': 'event_msg',
        'payload': {
            'type': 'assistant_message',
            'role': 'assistant',
            'message': 'reply',
        },
    }

    assert extract_event(entry) == ('assistant', 'reply')
