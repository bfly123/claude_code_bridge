from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from provider_backends.codex.comm_runtime.polling_runtime.reader_runtime.service_runtime import (
    read_matching_since,
)


def test_read_matching_since_returns_no_match_state_without_raising(tmp_path: Path) -> None:
    log_path = tmp_path / 'codex.log'
    log_path.write_text('', encoding='utf-8')
    reader = SimpleNamespace(_poll_interval=0.0, _preferred_log=None)

    match, state = read_matching_since(
        reader,
        {'log_path': log_path, 'offset': 0},
        timeout=0.0,
        block=False,
        extractor=lambda entry: entry,
        stop_on_missing_timeout=True,
    )

    assert match is None
    assert state['log_path'] == log_path
    assert state['offset'] == 0
