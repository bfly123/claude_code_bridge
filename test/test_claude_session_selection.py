from __future__ import annotations

import os
from pathlib import Path

from provider_backends.claude.comm import ClaudeLogReader


def _project_key(path: Path) -> str:
    return ''.join(ch if ch.isalnum() else '-' for ch in str(path))


def _write_session(path: Path, *, text: str = 'hello', sidechain: bool | None = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if sidechain is True:
        lines.append('{"isSidechain":true}\n')
    elif sidechain is None:
        lines.append('{"type":"assistant","message":{"role":"assistant","content":[]}}\n')
    lines.append(
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"'
        + text
        + '"}]}}\n'
    )
    path.write_text(''.join(lines), encoding='utf-8')


def test_latest_session_keeps_explicit_preferred_session_over_newer_candidate(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / 'claude-root'
    work_dir = tmp_path / 'project-a'
    work_dir.mkdir()
    monkeypatch.setenv('PWD', str(work_dir))

    older = root / _project_key(work_dir) / 'older.jsonl'
    newer = root / _project_key(work_dir) / 'newer.jsonl'
    _write_session(older, text='old')
    _write_session(newer, text='new')
    os.utime(older, (older.stat().st_atime, older.stat().st_mtime + 1))
    os.utime(newer, (newer.stat().st_atime, newer.stat().st_mtime + 20))

    reader = ClaudeLogReader(root=root, work_dir=work_dir, use_sessions_index=False)
    reader.set_preferred_session(older)

    assert reader._preferred_session == older
    assert reader._preferred_session_locked is True
    assert reader.current_session_path() == older


def test_active_reader_can_rotate_from_bound_session_after_claude_clear(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / 'claude-root'
    work_dir = tmp_path / 'project-a'
    work_dir.mkdir()
    monkeypatch.setenv('PWD', str(work_dir))

    original = root / _project_key(work_dir) / 'original.jsonl'
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_text(
        '{"type":"user","isSidechain":false,"message":{"role":"user","content":"old request"}}\n'
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"old"}]}}\n',
        encoding='utf-8',
    )

    reader = ClaudeLogReader(root=root, work_dir=work_dir, use_sessions_index=False)
    reader.set_preferred_session(original)
    state = reader.capture_state()
    reader.allow_preferred_session_rotation()

    rotated = root / _project_key(work_dir) / 'rotated.jsonl'
    rotated.write_text(
        '{"type":"summary","summary":"prior context"}\n'
        '{"type":"user","isSidechain":false,"message":{"role":"user","content":"new request"}}\n'
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"new"}]}}\n',
        encoding='utf-8',
    )
    os.utime(rotated, (rotated.stat().st_atime, original.stat().st_mtime + 20))

    entries, updated = reader.try_get_entries(state)

    assert reader._preferred_session_locked is False
    assert reader.current_session_path() == rotated
    assert updated['session_path'] == rotated
    assert [entry['text'] for entry in entries if entry['role'] == 'assistant'] == ['new']


def test_scan_latest_session_reads_sidechain_flag_after_summary_prelude(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / 'claude-root'
    work_dir = tmp_path / 'project-a'
    work_dir.mkdir()
    monkeypatch.setenv('PWD', str(work_dir))

    session = root / _project_key(work_dir) / 'session.jsonl'
    session.parent.mkdir(parents=True, exist_ok=True)
    session.write_text(
        '{"type":"summary","summary":"prior context"}\n'
        '{"type":"user","isSidechain":false,"message":{"role":"user","content":"request"}}\n',
        encoding='utf-8',
    )

    reader = ClaudeLogReader(root=root, work_dir=work_dir, use_sessions_index=False)

    assert reader._session_is_sidechain(session) is False
    assert reader._scan_latest_session() == session


def test_session_is_sidechain_skips_file_history_snapshot_preamble(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / 'claude-root'
    work_dir = tmp_path / 'project-a'
    work_dir.mkdir()
    monkeypatch.setenv('PWD', str(work_dir))

    live = root / _project_key(work_dir) / 'live.jsonl'
    stale = root / _project_key(work_dir) / 'stale.jsonl'
    live.parent.mkdir(parents=True, exist_ok=True)
    preamble = '\n'.join(
        [
            '{"type":"ai-title","title":"demo"}',
            '{"type":"agent-name","name":"claude"}',
            '{"type":"mode","mode":"default"}',
            '{"type":"permission-mode","mode":"default"}',
            *[
                f'{{"type":"file-history-snapshot","messageId":"snap-{index}"}}'
                for index in range(30)
            ],
            '{"type":"user","isSidechain":false,"message":{"role":"user","content":"live"}}',
        ]
    ) + '\n'
    live.write_text(preamble, encoding='utf-8')
    stale.write_text(
        '{"type":"user","isSidechain":false,"message":{"role":"user","content":"stale"}}\n',
        encoding='utf-8',
    )
    os.utime(live, (live.stat().st_atime, live.stat().st_mtime + 20))

    reader = ClaudeLogReader(root=root, work_dir=work_dir, use_sessions_index=False)

    assert reader._session_is_sidechain(live) is False
    assert reader._scan_latest_session() == live


def test_latest_session_ignores_env_pwd_project_namespace_for_workspace_reader(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / 'claude-root'
    project_root = tmp_path / 'project-a'
    work_dir = project_root / '.ccb' / 'workspaces' / 'agent1'
    project_root.mkdir(parents=True)
    work_dir.mkdir(parents=True)
    monkeypatch.setenv('PWD', str(project_root))

    root_session = root / _project_key(project_root) / 'root.jsonl'
    workspace_session = root / _project_key(work_dir) / 'workspace.jsonl'
    _write_session(root_session, text='root')
    _write_session(workspace_session, text='workspace')
    os.utime(root_session, (root_session.stat().st_atime, root_session.stat().st_mtime + 20))

    reader = ClaudeLogReader(root=root, work_dir=work_dir, use_sessions_index=False)

    assert reader.current_session_path() == workspace_session


def test_scan_latest_session_skips_sidechain_when_normal_session_exists(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / 'claude-root'
    work_dir = tmp_path / 'project-a'
    work_dir.mkdir()
    monkeypatch.setenv('PWD', str(work_dir))

    normal = root / _project_key(work_dir) / 'normal.jsonl'
    sidechain = root / _project_key(work_dir) / 'sidechain.jsonl'
    _write_session(normal, text='normal', sidechain=False)
    _write_session(sidechain, text='side', sidechain=True)
    os.utime(normal, (normal.stat().st_atime, normal.stat().st_mtime + 1))
    os.utime(sidechain, (sidechain.stat().st_atime, sidechain.stat().st_mtime + 20))

    reader = ClaudeLogReader(root=root, work_dir=work_dir, use_sessions_index=False)

    assert reader._scan_latest_session() == normal


def test_latest_session_can_fallback_to_any_project_scan(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / 'claude-root'
    work_dir = tmp_path / 'project-a'
    other_dir = tmp_path / 'project-b'
    work_dir.mkdir()
    other_dir.mkdir()
    monkeypatch.setenv('PWD', str(work_dir))
    monkeypatch.setenv('CLAUDE_ALLOW_ANY_PROJECT_SCAN', '1')

    foreign = root / _project_key(other_dir) / 'foreign.jsonl'
    _write_session(foreign, text='foreign')

    reader = ClaudeLogReader(root=root, work_dir=work_dir, use_sessions_index=False)

    assert reader.current_session_path() == foreign
