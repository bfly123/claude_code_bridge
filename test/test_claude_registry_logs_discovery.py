from __future__ import annotations

import os
from pathlib import Path

from provider_backends.claude.registry_support.logs_runtime.discovery import (
    extract_session_id_from_start_cmd,
    find_log_for_session_id,
    scan_latest_log_for_work_dir,
)


def test_extract_session_id_from_start_cmd_finds_uuid() -> None:
    session_id = '12345678-1234-1234-1234-1234567890ab'

    assert extract_session_id_from_start_cmd(f'claude --resume {session_id}') == session_id
    assert extract_session_id_from_start_cmd('claude fresh') is None


def test_find_log_for_session_id_returns_newest_match(tmp_path: Path) -> None:
    root = tmp_path / 'claude-root'
    older = root / 'a' / '12345678-1234-1234-1234-1234567890ab.jsonl'
    newer = root / 'b' / 'session-12345678-1234-1234-1234-1234567890ab-copy.jsonl'
    older.parent.mkdir(parents=True, exist_ok=True)
    newer.parent.mkdir(parents=True, exist_ok=True)
    older.write_text('', encoding='utf-8')
    newer.write_text('', encoding='utf-8')
    os.utime(older, (older.stat().st_atime, older.stat().st_mtime + 1))
    os.utime(newer, (newer.stat().st_atime, newer.stat().st_mtime + 20))

    result = find_log_for_session_id('12345678-1234-1234-1234-1234567890ab', root=root)

    assert result == newer


def test_scan_latest_log_for_work_dir_skips_sidechain_and_returns_matching_log(tmp_path: Path) -> None:
    root = tmp_path / 'claude-root'
    work_dir = tmp_path / 'repo'
    work_dir.mkdir()
    older = root / 'a' / 'normal.jsonl'
    sidechain = root / 'a' / 'sidechain.jsonl'
    foreign = root / 'b' / 'foreign.jsonl'
    for path in (older, sidechain, foreign):
        path.parent.mkdir(parents=True, exist_ok=True)

    older.write_text(
        '{"cwd":"' + str(work_dir) + '","sessionId":"sid-normal","isSidechain":false}\n',
        encoding='utf-8',
    )
    sidechain.write_text(
        '{"cwd":"' + str(work_dir) + '","sessionId":"sid-side","isSidechain":true}\n',
        encoding='utf-8',
    )
    foreign.write_text(
        '{"cwd":"' + str(tmp_path / "other") + '","sessionId":"sid-foreign","isSidechain":false}\n',
        encoding='utf-8',
    )
    os.utime(older, (older.stat().st_atime, older.stat().st_mtime + 5))
    os.utime(sidechain, (sidechain.stat().st_atime, sidechain.stat().st_mtime + 20))
    os.utime(foreign, (foreign.stat().st_atime, foreign.stat().st_mtime + 10))

    log_path, session_id = scan_latest_log_for_work_dir(work_dir, root=root, scan_limit=10)

    assert log_path == older
    assert session_id == 'sid-normal'
