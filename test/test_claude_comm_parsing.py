from __future__ import annotations

from provider_backends.claude.comm_runtime.parsing import extract_content_text, extract_message, structured_event


def test_extract_content_text_ignores_thinking_fragments() -> None:
    content = [
        {"type": "thinking", "text": "internal"},
        {"type": "text", "content": "hello"},
        {"type": "text", "text": "world"},
    ]

    assert extract_content_text(content) == "hello\nworld"


def test_extract_message_supports_response_item_and_event_msg() -> None:
    response_item = {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "from-response"}],
        },
    }
    event_msg = {
        "type": "event_msg",
        "payload": {
            "type": "assistant_message",
            "role": "assistant",
            "text": "from-event",
        },
    }

    assert extract_message(response_item, "assistant") == "from-response"
    assert extract_message(event_msg, "assistant") == "from-event"


def test_structured_event_captures_assistant_stop_reason() -> None:
    entry = {
        "type": "assistant",
        "subtype": "completion",
        "uuid": "u-1",
        "parentUuid": "p-1",
        "message": {
            "role": "assistant",
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "done"}],
        },
    }

    assert structured_event(entry) == {
        "role": "assistant",
        "text": "done",
        "entry_type": "assistant",
        "subtype": "completion",
        "uuid": "u-1",
        "parent_uuid": "p-1",
        "stop_reason": "end_turn",
        "entry": entry,
    }
