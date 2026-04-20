from __future__ import annotations

import json
from pathlib import Path

from cli.kill_runtime.sessions import terminate_provider_session


def test_terminate_provider_session_kills_pane_and_marks_session_inactive(tmp_path: Path, monkeypatch, capsys) -> None:
    session_file = tmp_path / '.codex-session'
    session_file.write_text(json.dumps({'pane_id': '%7', 'active': True}), encoding='utf-8')
    killed: list[str] = []
    writes: list[tuple[Path, str]] = []

    class _Backend:
        def kill_pane(self, pane_id: str) -> None:
            killed.append(pane_id)

    monkeypatch.setattr('cli.kill_runtime.sessions.shutil.which', lambda name: '/usr/bin/tmux')
    monkeypatch.setattr('cli.kill_runtime.sessions.time.strftime', lambda fmt: '2026-04-06 12:00:00')

    terminate_provider_session(
        'codex',
        cwd=tmp_path,
        session_finder=lambda cwd, name: session_file,
        tmux_backend_factory=lambda: _Backend(),
        safe_write_session=lambda path, payload: writes.append((path, payload)) or (True, None),
    )

    assert killed == ['%7']
    assert writes
    payload = json.loads(writes[-1][1])
    assert payload['active'] is False
    assert payload['ended_at'] == '2026-04-06 12:00:00'
    assert 'session terminated' in capsys.readouterr().out


def test_terminate_provider_session_kills_tmux_session_pair(tmp_path: Path, monkeypatch) -> None:
    session_file = tmp_path / '.claude-session'
    session_file.write_text(json.dumps({'tmux_session': 'demo-session', 'active': True}), encoding='utf-8')
    run_calls: list[list[str]] = []

    monkeypatch.setattr('cli.kill_runtime.sessions.shutil.which', lambda name: '/usr/bin/tmux')
    monkeypatch.setattr('cli.kill_runtime.sessions.subprocess.run', lambda args, stderr=None: run_calls.append(args))

    terminate_provider_session(
        'claude',
        cwd=tmp_path,
        session_finder=lambda cwd, name: session_file,
        tmux_backend_factory=lambda: object(),
        safe_write_session=lambda path, payload: (True, None),
    )

    assert run_calls == [
        ['tmux', 'kill-session', '-t', 'demo-session'],
        ['tmux', 'kill-session', '-t', 'launcher-demo-session'],
    ]
