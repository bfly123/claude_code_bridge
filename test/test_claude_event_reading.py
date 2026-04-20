from __future__ import annotations

from provider_backends.claude.execution_runtime.event_reading import read_events, terminal_api_error_payload


def test_read_events_normalizes_entry_and_tuple_shapes() -> None:
    class EntryReader:
        def try_get_entries(self, state):
            return ([{'role': 'assistant', 'text': 'ok'}, 'skip'], {'cursor': 1})

    events, state = read_events(EntryReader(), {})
    assert events == [{'role': 'assistant', 'text': 'ok'}]
    assert state == {'cursor': 1}

    class TupleReader:
        def try_get_events(self, state):
            return ([('assistant', 'ok'), ('user', 'hi'), 'skip'], {'cursor': 2})

    events, state = read_events(TupleReader(), {})
    assert events == [{'role': 'assistant', 'text': 'ok'}, {'role': 'user', 'text': 'hi'}]
    assert state == {'cursor': 2}


def test_terminal_api_error_payload_only_returns_exhausted_retry() -> None:
    event = {
        'entry_type': 'system',
        'subtype': 'api_error',
        'entry': {
            'retryAttempt': 3,
            'maxRetries': 3,
            'timestamp': '2026-04-06T00:00:00Z',
            'cause': {'code': 'model_missing', 'path': '/model'},
        },
    }

    payload = terminal_api_error_payload(event)

    assert payload is not None
    assert payload['error_code'] == 'model_missing'
    assert payload['error_path'] == '/model'
    assert 'Claude API request failed' in payload['message']

