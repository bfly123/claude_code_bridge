from __future__ import annotations

from types import SimpleNamespace

from provider_core.session_binding_evidence_runtime.pane import inspect_session_pane


def test_inspect_session_pane_reports_missing_for_marker_without_pane(monkeypatch) -> None:
    session = SimpleNamespace(terminal='tmux', pane_id='', pane_title_marker='agent1')

    monkeypatch.setattr('provider_core.session_binding_evidence_runtime.pane.session_backend', lambda session: object())
    monkeypatch.setattr('provider_core.session_binding_evidence_runtime.pane.session_pane_title_marker', lambda session: 'agent1')

    payload = inspect_session_pane(session)

    assert payload['pane_state'] == 'missing'
    assert payload['active_pane_id'] is None


def test_inspect_session_pane_reports_foreign_tmux_pane(monkeypatch) -> None:
    class Backend:
        def pane_exists(self, pane_id):
            return True

    session = SimpleNamespace(terminal='tmux', pane_id='%1', pane_title_marker='agent1')

    monkeypatch.setattr('provider_core.session_binding_evidence_runtime.pane.session_backend', lambda session: Backend())
    monkeypatch.setattr('provider_core.session_binding_evidence_runtime.pane.session_pane_title_marker', lambda session: 'agent1')
    monkeypatch.setattr(
        'provider_core.session_binding_evidence_runtime.pane.inspect_tmux_pane_ownership',
        lambda session, backend, pane_id: SimpleNamespace(is_owned=False),
    )

    payload = inspect_session_pane(session)

    assert payload['pane_state'] == 'foreign'
    assert payload['active_pane_id'] is None
