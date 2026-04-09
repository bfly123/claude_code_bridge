from __future__ import annotations

import json
from pathlib import Path

from provider_backends.droid.comm_runtime.binding import remember_droid_session_binding


def test_remember_droid_session_binding_records_previous_binding_and_project_id(tmp_path: Path) -> None:
    project_session_file = tmp_path / '.ccb' / '.droid-agent4-session'
    project_session_file.parent.mkdir(parents=True, exist_ok=True)
    work_dir = tmp_path / 'repo'
    work_dir.mkdir()
    project_session_file.write_text(
        json.dumps(
            {
                'work_dir': str(work_dir),
                'droid_session_path': '/tmp/old-session.json',
                'droid_session_id': 'old-session',
            },
            ensure_ascii=False,
            indent=2,
        )
        + '\n',
        encoding='utf-8',
    )
    session_path = tmp_path / 'sessions' / 'new-session.json'

    result = remember_droid_session_binding(
        project_session_file=project_session_file,
        session_path=session_path,
        session_id_loader=lambda path: (None, 'new-session'),
    )

    assert result is not None
    assert result['droid_session_path'] == str(session_path)
    assert result['droid_session_id'] == 'new-session'
    assert result['old_droid_session_path'] == '/tmp/old-session.json'
    assert result['old_droid_session_id'] == 'old-session'
    assert result['ccb_project_id']
    persisted = json.loads(project_session_file.read_text(encoding='utf-8'))
    assert persisted['droid_session_id'] == 'new-session'


def test_remember_droid_session_binding_returns_existing_data_when_unchanged(tmp_path: Path) -> None:
    project_session_file = tmp_path / '.ccb' / '.droid-agent4-session'
    project_session_file.parent.mkdir(parents=True, exist_ok=True)
    project_session_file.write_text(
        json.dumps(
            {
                'work_dir': str(tmp_path / 'repo'),
                'droid_session_path': '/tmp/current.json',
                'droid_session_id': 'same-id',
                'ccb_project_id': 'pid-1',
            },
            ensure_ascii=False,
            indent=2,
        )
        + '\n',
        encoding='utf-8',
    )

    result = remember_droid_session_binding(
        project_session_file=project_session_file,
        session_path=Path('/tmp/current.json'),
        session_id_loader=lambda path: (None, 'same-id'),
    )

    assert result is not None
    assert result['droid_session_id'] == 'same-id'
    assert 'old_droid_session_id' not in result
