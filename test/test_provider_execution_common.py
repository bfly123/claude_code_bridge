from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from completion.models import CompletionItemKind, CompletionSourceKind
from provider_execution.common import (
    build_item,
    deserialize_runtime_state,
    is_runtime_target_alive,
    preferred_session_path,
    request_anchor_from_runtime_state,
    send_prompt_to_runtime_target,
    serialize_runtime_state,
)


def test_build_item_and_request_anchor_from_runtime_state() -> None:
    submission = SimpleNamespace(
        source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM,
        provider='codex',
        agent_name='agent1',
        job_id='job_1',
    )

    item = build_item(
        submission,
        kind=CompletionItemKind.RESULT,
        timestamp='2026-04-05T00:00:00Z',
        seq=3,
        payload={'text': 'hello'},
    )

    assert item.req_id == 'job_1'
    assert item.cursor.event_seq == 3
    assert request_anchor_from_runtime_state({'request_anchor': 'req_1'}, fallback='job_1') == 'req_1'
    assert request_anchor_from_runtime_state(None, fallback='job_1') == 'job_1'


def test_preferred_session_path_rejects_non_path_like_refs() -> None:
    assert preferred_session_path('', 'session-id-123') is None
    assert preferred_session_path('/tmp/demo.json', None) == Path('/tmp/demo.json')
    assert preferred_session_path('', '~/demo.jsonl') == Path('~/demo.jsonl').expanduser()


def test_runtime_state_serialization_roundtrip_preserves_supported_types(tmp_path: Path) -> None:
    payload = {
        'path': tmp_path / 'demo.json',
        'blob': b'abc',
        'items': [1, ('two', 3)],
    }

    encoded = serialize_runtime_state(payload)
    decoded = deserialize_runtime_state(encoded)

    assert decoded == {
        'path': (tmp_path / 'demo.json').expanduser(),
        'blob': b'abc',
        'items': [1, ('two', 3)],
    }


def test_runtime_target_helpers_use_available_backend_methods() -> None:
    sent: list[tuple[str, str]] = []

    class Backend:
        def send_text(self, pane_id: str, text: str) -> None:
            sent.append((pane_id, text))

        def is_alive(self, pane_id: str) -> bool:
            return pane_id == '%7'

    backend = Backend()
    send_prompt_to_runtime_target(backend, '%7', 'hello')

    assert sent == [('%7', 'hello')]
    assert is_runtime_target_alive(backend, '%7') is True
    assert is_runtime_target_alive(backend, '%8') is False
