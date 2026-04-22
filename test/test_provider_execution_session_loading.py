from __future__ import annotations

import json
from pathlib import Path

from provider_backends.claude import execution as claude_execution
from provider_backends.codex import execution as codex_execution
from provider_backends.gemini import execution as gemini_execution


def _write_session(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def test_claude_execution_loader_falls_back_to_explicit_session_file(monkeypatch, tmp_path: Path) -> None:
    session_file = tmp_path / 'runtime' / 'claude-session.json'
    _write_session(
        session_file,
        {
            'pane_id': '%2',
            'work_dir': str(tmp_path),
            'claude_session_path': str(tmp_path / 'claude-session.jsonl'),
        },
    )
    monkeypatch.setattr(claude_execution, 'load_project_session', lambda work_dir, instance=None: None)

    session = claude_execution._load_session(
        tmp_path / 'workspace',
        agent_name='agent1',
        session_file=str(session_file),
    )

    assert session is not None
    assert session.session_file == session_file
    assert session.work_dir == str(tmp_path)


def test_codex_execution_loader_falls_back_to_explicit_session_file(monkeypatch, tmp_path: Path) -> None:
    session_file = tmp_path / 'runtime' / 'codex-session.json'
    _write_session(
        session_file,
        {
            'pane_id': '%3',
            'work_dir': str(tmp_path),
            'codex_session_path': str(tmp_path / 'codex-session.jsonl'),
            'codex_session_id': 'codex-sid',
        },
    )
    monkeypatch.setattr(codex_execution, 'load_project_session', lambda work_dir, instance=None: None)

    session = codex_execution._load_session(
        tmp_path / 'workspace',
        agent_name='agent1',
        session_file=str(session_file),
    )

    assert session is not None
    assert session.session_file == session_file
    assert session.codex_session_id == 'codex-sid'


def test_gemini_execution_loader_falls_back_to_explicit_session_file(monkeypatch, tmp_path: Path) -> None:
    session_file = tmp_path / 'runtime' / 'gemini-session.json'
    _write_session(
        session_file,
        {
            'pane_id': '%4',
            'work_dir': str(tmp_path),
            'gemini_session_path': str(tmp_path / 'gemini-session.json'),
            'gemini_session_id': 'gemini-sid',
        },
    )
    monkeypatch.setattr(gemini_execution, 'load_project_session', lambda work_dir, instance=None: None)

    session = gemini_execution._load_session(
        tmp_path / 'workspace',
        agent_name='agent1',
        session_file=str(session_file),
    )

    assert session is not None
    assert session.session_file == session_file
    assert session.gemini_session_id == 'gemini-sid'
