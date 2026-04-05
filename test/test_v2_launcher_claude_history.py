from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

from launcher.claude_history import ClaudeHistoryLocator


def _project_key(path: Path) -> str:
    return ''.join(ch if ch.isalnum() else '-' for ch in str(path))


def test_claude_history_locator_prefers_pwd_project_dir(tmp_path: Path) -> None:
    home_dir = tmp_path / 'home'
    projects_root = home_dir / '.claude' / 'projects'
    env_pwd = tmp_path / 'logical-project'
    work_dir = tmp_path / 'physical-project'
    pwd_project_dir = projects_root / _project_key(env_pwd)
    pwd_project_dir.mkdir(parents=True)

    locator = ClaudeHistoryLocator(
        invocation_dir=work_dir,
        project_root=work_dir,
        env={'PWD': str(env_pwd)},
        home_dir=home_dir,
    )

    assert locator.project_dir(work_dir) == pwd_project_dir


def test_claude_history_locator_returns_latest_valid_uuid_session(tmp_path: Path) -> None:
    home_dir = tmp_path / 'home'
    work_dir = tmp_path / 'project'
    project_dir = home_dir / '.claude' / 'projects' / _project_key(work_dir)
    session_env_root = home_dir / '.claude' / 'session-env'
    project_dir.mkdir(parents=True)
    session_env_root.mkdir(parents=True)

    older = str(uuid.uuid4())
    newer = str(uuid.uuid4())
    older_file = project_dir / f'{older}.jsonl'
    newer_file = project_dir / f'{newer}.jsonl'
    older_file.write_text('old\n', encoding='utf-8')
    newer_file.write_text('new\n', encoding='utf-8')
    (session_env_root / older).mkdir()
    (session_env_root / newer).mkdir()
    os.utime(older_file, (time.time() - 10, time.time() - 10))
    os.utime(newer_file, None)

    locator = ClaudeHistoryLocator(
        invocation_dir=work_dir,
        project_root=work_dir,
        env={},
        home_dir=home_dir,
    )

    session_id, has_history, best_cwd = locator.latest_session_id()

    assert session_id == newer
    assert has_history is True
    assert best_cwd == work_dir


def test_claude_history_locator_reports_history_without_valid_resume_session(tmp_path: Path) -> None:
    home_dir = tmp_path / 'home'
    work_dir = tmp_path / 'project'
    project_dir = home_dir / '.claude' / 'projects' / _project_key(work_dir)
    project_dir.mkdir(parents=True)
    (project_dir / 'not-a-uuid.jsonl').write_text('history\n', encoding='utf-8')

    locator = ClaudeHistoryLocator(
        invocation_dir=work_dir,
        project_root=work_dir,
        env={},
        home_dir=home_dir,
    )

    session_id, has_history, best_cwd = locator.latest_session_id()

    assert session_id is None
    assert has_history is True
    assert best_cwd == work_dir
