from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from provider_backends.opencode.runtime.reply_polling import find_new_assistant_reply_with_reader_state, read_since


def test_opencode_find_new_assistant_reply_updates_completed_timestamp(monkeypatch) -> None:
    reader = SimpleNamespace(_extract_text=lambda parts, allow_reasoning_fallback=True: 'done CCB_DONE: job_1')
    monkeypatch.setattr(
        'provider_backends.opencode.runtime.reply_polling_runtime.service.read_messages',
        lambda reader, session_id: [{'id': 'msg_1', 'role': 'assistant', 'time': {}}],
    )
    monkeypatch.setattr(
        'provider_backends.opencode.runtime.reply_polling_runtime.service.read_parts',
        lambda reader, message_id: [{'type': 'text', 'text': 'done CCB_DONE: job_1'}],
    )
    monkeypatch.setattr(
        'provider_backends.opencode.runtime.reply_polling_runtime.service.time.time',
        lambda: 1234.5,
    )

    reply, state = find_new_assistant_reply_with_reader_state(reader, 'ses_1', {})

    assert reply == 'done CCB_DONE: job_1'
    assert state is not None
    assert state['last_assistant_completed'] == 1234500


def test_opencode_read_since_returns_reply_when_session_updates(monkeypatch) -> None:
    reader = SimpleNamespace(_poll_interval=0.0, _force_read_interval=10.0, _extract_text=lambda parts, allow_reasoning_fallback=True: 'done')
    monkeypatch.setattr(
        'provider_backends.opencode.runtime.reply_polling_runtime.service.get_latest_session',
        lambda reader: {'path': '/tmp/ses_1', 'payload': {'id': 'ses_1', 'time': {'updated': 7}}},
    )
    monkeypatch.setattr(
        'provider_backends.opencode.runtime.reply_polling_runtime.service.find_new_assistant_reply_with_reader_state',
        lambda reader, session_id, state: ('reply text', {'assistant_count': 1}),
    )

    reply, state = read_since(reader, {}, timeout=0.0, block=False)

    assert reply == 'reply text'
    assert state['session_id'] == 'ses_1'
    assert state['session_updated'] == 7
    assert state['assistant_count'] == 1


def test_opencode_read_since_returns_none_when_no_session_and_non_blocking() -> None:
    reader = SimpleNamespace(_poll_interval=0.0, _force_read_interval=10.0)
    monkeypatch_target = 'provider_backends.opencode.runtime.reply_polling_runtime.service.get_latest_session'
    import provider_backends.opencode.runtime.reply_polling_runtime.service as service
    service.get_latest_session = lambda reader: None

    reply, state = read_since(reader, {'session_id': 'old'}, timeout=0.0, block=False)

    assert reply is None
    assert state == {'session_id': 'old'}
