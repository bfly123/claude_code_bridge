from __future__ import annotations

from types import SimpleNamespace

from provider_backends.opencode.runtime.reply_polling import find_new_assistant_reply_with_reader_state, read_since


def test_opencode_find_new_assistant_reply_reads_completed_binding_from_storage(monkeypatch) -> None:
    reader = SimpleNamespace(_extract_req_id_from_text=lambda text: 'job_1')
    monkeypatch.setattr(
        'provider_backends.opencode.runtime.reply_polling_runtime.service.read_messages',
        lambda reader, session_id: [
            {'id': 'msg_user', 'role': 'user'},
            {'id': 'msg_1', 'role': 'assistant', 'parentID': 'msg_user', 'time': {'completed': 1234}},
        ],
    )
    monkeypatch.setattr(
        'provider_backends.opencode.runtime.reply_polling_runtime.service.read_parts',
        lambda reader, message_id: [{'type': 'text', 'text': 'CCB_REQ_ID: job_1'}]
        if message_id == 'msg_user'
        else [{'type': 'text', 'text': 'done'}],
    )

    reply, state = find_new_assistant_reply_with_reader_state(reader, 'ses_1', {})

    assert reply == 'done'
    assert state is not None
    assert state['last_assistant_completed'] == 1234
    assert state['last_assistant_req_id'] == 'job_1'
    assert state['last_assistant_parent_id'] == 'msg_user'


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
