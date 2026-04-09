from __future__ import annotations

from types import SimpleNamespace

from provider_backends.pane_log_support import session as pane_session


def test_compute_session_key_for_provider_uses_bound_project_id_and_scope(monkeypatch) -> None:
    monkeypatch.setattr(pane_session, 'compute_worktree_scope_id', lambda _path: 'scope-7')
    session = SimpleNamespace(data={'ccb_project_id': 'proj-1'}, work_dir='/tmp/demo')

    key = pane_session.compute_session_key_for_provider(
        session,
        provider='codex',
        instance='agent2',
    )

    assert key == 'codex:agent2:proj-1:scope-7'


def test_compute_session_key_for_provider_falls_back_to_unknown_project(monkeypatch) -> None:
    def _raise(_path):
        raise RuntimeError('no project')

    monkeypatch.setattr(pane_session, 'compute_ccb_project_id', _raise)
    monkeypatch.setattr(pane_session, 'compute_worktree_scope_id', lambda _path: 'scope-7')
    session = SimpleNamespace(data={}, work_dir='/tmp/demo')

    key = pane_session.compute_session_key_for_provider(session, provider='codex')

    assert key == 'codex:unknown:scope-7'
