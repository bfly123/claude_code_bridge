from __future__ import annotations

from provider_backends.pane_log_support.parsing import (
    extract_assistant_blocks,
    extract_conversation_pairs,
)


def test_extract_assistant_blocks_returns_plain_text_without_protocol_markers() -> None:
    assert extract_assistant_blocks('  hello world  ') == ['hello world']


def test_extract_assistant_blocks_collects_each_protocol_segment() -> None:
    text = (
        'user1\n'
        'CCB_REQ_ID: job_1\n'
        'assistant one\n'
        'CCB_DONE: job_1\n'
        'user2\n'
        'CCB_REQ_ID: job_2\n'
        'assistant two\n'
    )

    assert extract_assistant_blocks(text) == ['assistant one', 'assistant two']


def test_extract_conversation_pairs_preserves_user_and_assistant_segments() -> None:
    text = (
        'first user\n'
        'CCB_REQ_ID: job_1\n'
        'first assistant\n'
        'CCB_DONE: job_1\n'
        'second user\n'
        'CCB_REQ_ID: job_2\n'
        'second assistant\n'
    )

    assert extract_conversation_pairs(text) == [
        ('first user', 'first assistant'),
        ('CCB_DONE: job_1\nsecond user', 'second assistant'),
    ]
