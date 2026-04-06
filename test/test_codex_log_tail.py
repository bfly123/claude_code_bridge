from __future__ import annotations

from provider_backends.codex.comm_runtime.session_selection import iter_lines_reverse


def test_iter_lines_reverse_returns_latest_nonempty_lines(tmp_path) -> None:
    log_path = tmp_path / "session.jsonl"
    log_path.write_text("first\n\nsecond\nthird\n", encoding="utf-8")

    lines = iter_lines_reverse(object(), log_path, max_bytes=1024, max_lines=2)

    assert lines == ["third", "second"]


def test_iter_lines_reverse_returns_empty_when_limits_disable_read(tmp_path) -> None:
    log_path = tmp_path / "session.jsonl"
    log_path.write_text("line\n", encoding="utf-8")

    assert iter_lines_reverse(object(), log_path, max_bytes=0, max_lines=5) == []
    assert iter_lines_reverse(object(), log_path, max_bytes=128, max_lines=0) == []
