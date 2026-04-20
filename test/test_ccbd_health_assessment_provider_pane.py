from __future__ import annotations

from types import SimpleNamespace

from ccbd.services.health_assessment.provider_pane import assess_provider_pane


def _runtime(**overrides):
    values = {
        'runtime_ref': 'tmux:%1',
        'agent_name': 'agent1',
        'workspace_path': '/tmp/workspace',
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _registry(provider: str = 'codex'):
    return SimpleNamespace(spec_for=lambda agent_name: SimpleNamespace(provider=provider))


def _binding():
    return SimpleNamespace(load_session=lambda workspace_path, agent_name: None)


def test_assess_provider_pane_reports_missing_session(monkeypatch) -> None:
    binding = _binding()
    monkeypatch.setattr(
        'ccbd.services.health_assessment.provider_pane.load_provider_session',
        lambda binding, workspace_path, agent_name: None,
    )

    assessment = assess_provider_pane(
        runtime=_runtime(),
        registry=_registry(),
        session_bindings={'codex': binding},
        namespace_state_store=object(),
    )

    assert assessment is not None
    assert assessment.binding is binding
    assert assessment.session is None
    assert assessment.pane_state == 'missing'
    assert assessment.health == 'session-missing'


def test_assess_provider_pane_marks_foreign_tmux_pane(monkeypatch) -> None:
    binding = _binding()
    session = SimpleNamespace(pane_id='%9')
    monkeypatch.setattr(
        'ccbd.services.health_assessment.provider_pane.load_provider_session',
        lambda binding, workspace_path, agent_name: session,
    )
    monkeypatch.setattr(
        'ccbd.services.health_assessment.provider_pane.session_terminal',
        lambda session: 'tmux',
    )
    monkeypatch.setattr(
        'ccbd.services.health_assessment.provider_pane.session_backend',
        lambda session: 'backend',
    )
    monkeypatch.setattr(
        'ccbd.services.health_assessment.provider_pane.tmux_pane_state',
        lambda session, backend, pane_id: 'alive',
    )
    monkeypatch.setattr(
        'ccbd.services.health_assessment.provider_pane.pane_outside_project_namespace',
        lambda **kwargs: True,
    )

    assessment = assess_provider_pane(
        runtime=_runtime(),
        registry=_registry(),
        session_bindings={'codex': binding},
        namespace_state_store=object(),
    )

    assert assessment is not None
    assert assessment.session is session
    assert assessment.terminal == 'tmux'
    assert assessment.pane_state == 'foreign'
    assert assessment.health == 'pane-foreign'
