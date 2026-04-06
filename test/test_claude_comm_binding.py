from __future__ import annotations

import json
from pathlib import Path

from provider_backends.claude.comm_runtime.binding import (
    publish_claude_registry,
    remember_claude_session_binding,
)


def test_remember_claude_session_binding_updates_binding_and_keeps_old_values(tmp_path: Path) -> None:
    project_session_file = tmp_path / '.claude-session'
    project_session_file.write_text(
        json.dumps(
            {
                'work_dir': str(tmp_path / 'repo'),
                'claude_session_id': 'old-id',
                'claude_session_path': str(tmp_path / 'old-id.jsonl'),
            }
        ),
        encoding='utf-8',
    )
    session_path = tmp_path / 'new-id.jsonl'

    data = remember_claude_session_binding(
        project_session_file=project_session_file,
        session_path=session_path,
        session_info={'work_dir': str(tmp_path / 'repo')},
    )

    assert data is not None
    assert data['claude_session_id'] == 'new-id'
    assert data['claude_session_path'] == str(session_path)
    assert data['old_claude_session_id'] == 'old-id'
    assert data['old_claude_session_path'] == str(tmp_path / 'old-id.jsonl')
    assert data['active'] is True

    persisted = json.loads(project_session_file.read_text(encoding='utf-8'))
    assert persisted['claude_session_id'] == 'new-id'
    assert persisted['old_claude_session_id'] == 'old-id'


def test_publish_claude_registry_uses_explicit_project_id_and_work_dir(monkeypatch, tmp_path: Path) -> None:
    captured: list[dict[str, object]] = []

    monkeypatch.setattr(
        'provider_backends.claude.comm_runtime.binding.upsert_registry',
        lambda payload: captured.append(payload),
    )
    monkeypatch.setattr(
        'provider_backends.claude.comm_runtime.binding.compute_ccb_project_id',
        lambda work_dir: 'computed-project-id',
    )

    publish_claude_registry(
        session_info={
            'ccb_session_id': 'sess-1',
            'ccb_project_id': 'proj-1',
            'work_dir': str(tmp_path / 'repo'),
            'pane_title_marker': 'agent1',
            'claude_session_id': 'claude-1',
            'claude_session_path': str(tmp_path / 'claude-1.jsonl'),
        },
        terminal='tmux',
        pane_id='%1',
        project_session_file=str(tmp_path / '.claude-session'),
    )

    assert captured == [
        {
            'ccb_session_id': 'sess-1',
            'ccb_project_id': 'proj-1',
            'work_dir': str(tmp_path / 'repo'),
            'terminal': 'tmux',
            'providers': {
                'claude': {
                    'pane_id': '%1',
                    'pane_title_marker': 'agent1',
                    'session_file': str(tmp_path / '.claude-session'),
                    'claude_session_id': 'claude-1',
                    'claude_session_path': str(tmp_path / 'claude-1.jsonl'),
                }
            },
        }
    ]
