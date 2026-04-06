from __future__ import annotations

from pathlib import Path

from provider_backends.codex.comm_runtime.log_reader_facade import CodexLogReader
from provider_backends.codex.comm_runtime.session_content import latest_conversations, latest_message


def _write_log(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def test_codex_latest_message_reads_latest_assistant_message(tmp_path: Path) -> None:
    root = tmp_path / 'codex-root'
    log_path = root / '2026' / '04' / 'session.jsonl'
    _write_log(
        log_path,
        [
            '{"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"hello"}]}}',
            '{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"world"}]}}',
        ],
    )
    reader = CodexLogReader(root=root, log_path=log_path)

    assert latest_message(reader) == 'world'


def test_codex_latest_conversations_pairs_user_and_assistant_messages(tmp_path: Path) -> None:
    root = tmp_path / 'codex-root'
    log_path = root / '2026' / '04' / 'session.jsonl'
    _write_log(
        log_path,
        [
            '{"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"q1"}]}}',
            '{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"a1"}]}}',
            '{"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"q2"}]}}',
            '{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"a2"}]}}',
        ],
    )
    reader = CodexLogReader(root=root, log_path=log_path)

    assert latest_conversations(reader, n=1) == [('q2', 'a2')]
    assert latest_conversations(reader, n=2) == [('q1', 'a1'), ('q2', 'a2')]


def test_codex_latest_conversations_returns_empty_for_non_positive_n(tmp_path: Path) -> None:
    root = tmp_path / 'codex-root'
    log_path = root / '2026' / '04' / 'session.jsonl'
    _write_log(log_path, [])
    reader = CodexLogReader(root=root, log_path=log_path)

    assert latest_conversations(reader, n=0) == []
