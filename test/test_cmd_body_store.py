from __future__ import annotations

from pathlib import Path

from ccbd.services.dispatcher_runtime.reply_delivery_runtime.cmd_body_store import (
    body_file_path,
    reply_body_dir,
    write_reply_body,
)


def test_reply_body_dir_is_isolated_from_history(tmp_path: Path) -> None:
    # The ctx-transfer namespace lives at .ccb/history/; reply bodies must not
    # collide with it.
    d = reply_body_dir(tmp_path)
    assert d == tmp_path / '.ccb' / 'replies' / 'cmd'
    assert 'history' not in d.parts


def test_body_file_path_sanitizes_separators(tmp_path: Path) -> None:
    p = body_file_path(tmp_path, 'rep_abc/def\\ghi')
    assert p.name == 'rep_abc_def_ghi.md'
    assert p.parent == reply_body_dir(tmp_path)


def test_write_reply_body_creates_dir_and_writes_atomically(tmp_path: Path) -> None:
    target = write_reply_body(tmp_path, 'rep_001', 'hello body')
    assert target.exists()
    assert target.read_text(encoding='utf-8') == 'hello body'
    assert target.parent == reply_body_dir(tmp_path)


def test_write_reply_body_is_idempotent_on_overwrite(tmp_path: Path) -> None:
    first = write_reply_body(tmp_path, 'rep_002', 'first')
    second = write_reply_body(tmp_path, 'rep_002', 'second')
    assert first == second
    assert second.read_text(encoding='utf-8') == 'second'
