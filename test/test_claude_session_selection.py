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
