from __future__ import annotations

from pathlib import Path

from provider_backends.codex.comm_runtime.log_reader_facade import CodexLogReader
from provider_backends.codex.comm_runtime.polling_runtime.reader import read_entry_since, read_event_since, read_since


def _write_log(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def test_codex_read_since_returns_message_and_state(tmp_path: Path) -> None:
    root = tmp_path / 'codex-root'
    log_path = root / '2026' / '04' / 'session.jsonl'
    _write_log(
        log_path,
        ['{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"done"}]}}'],
    )
    reader = CodexLogReader(root=root, log_path=log_path)

    message, state = read_since(reader, {}, timeout=0.0, block=False)

    assert message == 'done'
    assert state['log_path'] == log_path
    assert state['offset'] > 0


def test_codex_read_event_since_skips_non_message_entries(tmp_path: Path) -> None:
    root = tmp_path / 'codex-root'
    log_path = root / '2026' / '04' / 'session.jsonl'
    _write_log(
        log_path,
        [
            '{"type":"event_msg","payload":{"type":"task_complete","last_agent_message":"done"}}',
            '{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"reply"}]}}',
        ],
    )
    reader = CodexLogReader(root=root, log_path=log_path)

    event, state = read_event_since(reader, {}, timeout=0.0, block=False)

    assert event == ('assistant', 'reply')
    assert state['offset'] > 0


def test_codex_read_entry_since_returns_none_when_log_missing(tmp_path: Path) -> None:
    reader = CodexLogReader(root=tmp_path / 'missing-root')

    entry, state = read_entry_since(reader, {}, timeout=0.0, block=False)

    assert entry is None
    assert state['log_path'] is None
    assert state['offset'] == 0
