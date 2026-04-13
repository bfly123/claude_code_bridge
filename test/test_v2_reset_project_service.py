from __future__ import annotations

from pathlib import Path

import pytest

from cli.services.reset_project import reset_project_state


def test_reset_project_state_preserves_only_ccb_config(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-reset'
    ccb_dir = project_root / '.ccb'
    ccb_dir.mkdir(parents=True)
    (ccb_dir / 'ccb.config').write_text('cmd; agent1:codex, agent2:claude\n', encoding='utf-8')
    (ccb_dir / 'ccbd' / 'state.json').parent.mkdir(parents=True, exist_ok=True)
    (ccb_dir / 'ccbd' / 'state.json').write_text('{}', encoding='utf-8')
    (ccb_dir / 'agents' / 'agent1' / 'runtime.json').parent.mkdir(parents=True, exist_ok=True)
    (ccb_dir / 'agents' / 'agent1' / 'runtime.json').write_text('{}', encoding='utf-8')
    (ccb_dir / 'workspaces' / 'agent1' / 'memory.txt').parent.mkdir(parents=True, exist_ok=True)
    (ccb_dir / 'workspaces' / 'agent1' / 'memory.txt').write_text('old', encoding='utf-8')
    (ccb_dir / '.codex-agent1-session').write_text('session', encoding='utf-8')

    seen: dict[str, object] = {}

    def _fake_stop(context) -> None:
        seen['project_root'] = context.project.project_root

    monkeypatch.setattr('cli.services.reset_project._stop_project_runtime', _fake_stop)

    summary = reset_project_state(project_root)

    assert summary.reset_performed is True
    assert summary.preserved_config is True
    assert seen['project_root'] == project_root.resolve()
    assert ccb_dir.is_dir()
    assert (ccb_dir / 'ccb.config').read_text(encoding='utf-8') == 'cmd; agent1:codex, agent2:claude\n'
    assert sorted(path.relative_to(ccb_dir).as_posix() for path in ccb_dir.rglob('*') if path.is_file()) == ['ccb.config']


def test_reset_project_state_fails_fast_when_runtime_cleanup_cannot_stop_project(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-reset-fails'
    ccb_dir = project_root / '.ccb'
    ccb_dir.mkdir(parents=True)
    (ccb_dir / 'ccb.config').write_text('cmd; agent1:codex\n', encoding='utf-8')
    (ccb_dir / 'agents' / 'agent1' / 'runtime.json').parent.mkdir(parents=True, exist_ok=True)
    (ccb_dir / 'agents' / 'agent1' / 'runtime.json').write_text('{}', encoding='utf-8')

    def _raise(label: str):
        def _inner(*args, **kwargs):
            del args, kwargs
            raise RuntimeError(f'{label} failed')
        return _inner

    class _FailingNamespaceController:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def destroy(self, *args, **kwargs) -> None:
            del args, kwargs
            raise RuntimeError('namespace failed')

    monkeypatch.setattr('cli.services.reset_project.kill_project', _raise('kill'))
    monkeypatch.setattr('cli.services.reset_project.shutdown_daemon', _raise('shutdown'))
    monkeypatch.setattr('cli.services.reset_project.ProjectNamespaceController', _FailingNamespaceController)

    with pytest.raises(RuntimeError, match='ccb kill -f'):
        reset_project_state(project_root)

    assert ccb_dir.is_dir()
    assert (ccb_dir / 'ccb.config').read_text(encoding='utf-8') == 'cmd; agent1:codex\n'
    assert (ccb_dir / 'agents' / 'agent1' / 'runtime.json').is_file()
