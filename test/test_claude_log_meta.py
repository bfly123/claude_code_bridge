from __future__ import annotations

from pathlib import Path

from provider_backends.claude.registry_support.logs_runtime.meta import read_session_meta


def test_read_session_meta_returns_first_valid_meta_tuple(tmp_path: Path) -> None:
    log_path = tmp_path / "session.jsonl"
    log_path.write_text(
        '{"ignored": true}\n'
        '{"cwd": "/tmp/demo", "sessionId": "sid-1", "isSidechain": true}\n',
        encoding="utf-8",
    )

    assert read_session_meta(log_path) == ("/tmp/demo", "sid-1", True)
