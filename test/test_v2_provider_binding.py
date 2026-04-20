from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cli.services.provider_binding import resolve_agent_binding
from provider_core.contracts import ProviderRuntimeIdentity, ProviderSessionBinding


@dataclass
class _FakeSession:
    pane_id: str
    terminal: str = 'tmux'
    fake_session_id: str = 'session-1'
    ensure_ok: bool = True
    backend_obj: object | None = None
    data: dict | None = None

    def ensure_pane(self):
        if self.ensure_ok:
            self.pane_id = '%99'
            return True, self.pane_id
        return False, 'pane_dead'

    def backend(self):
        return self.backend_obj


def test_resolve_agent_binding_uses_ensure_pane_and_returns_updated_runtime_ref(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session = _FakeSession(pane_id='%41', fake_session_id='session-1', ensure_ok=True)
    adapter = ProviderSessionBinding(
        provider='codex',
        load_session=lambda root, instance: session,
        session_id_attr='fake_session_id',
        session_path_attr='fake_session_path',
    )

    monkeypatch.setattr('cli.services.provider_binding._binding_adapter', lambda provider: adapter)

    binding = resolve_agent_binding(
        provider='codex',
        agent_name='agent1',
        workspace_path=tmp_path / 'workspace',
        project_root=tmp_path / 'project',
        ensure_usable=True,
    )

    assert binding is not None
    assert binding.runtime_ref == 'tmux:%99'
    assert binding.session_ref == 'session-1'
    assert binding.tmux_socket_name is None
    assert binding.terminal == 'tmux'
    assert binding.pane_id == '%99'
    assert binding.active_pane_id == '%99'
    assert binding.pane_state == 'alive'


def test_resolve_agent_binding_rejects_session_when_ensure_pane_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session = _FakeSession(pane_id='%41', fake_session_id='session-1', ensure_ok=False)
    adapter = ProviderSessionBinding(
        provider='codex',
        load_session=lambda root, instance: session,
        session_id_attr='fake_session_id',
        session_path_attr='fake_session_path',
    )

    monkeypatch.setattr('cli.services.provider_binding._binding_adapter', lambda provider: adapter)

    binding = resolve_agent_binding(
        provider='codex',
        agent_name='agent1',
        workspace_path=tmp_path / 'workspace',
        project_root=tmp_path / 'project',
        ensure_usable=True,
    )

    assert binding is None


def test_resolve_agent_binding_rejects_session_when_pane_dies_during_stability_check(
    tmp_path: Path,
    monkeypatch,
) -> None:
    checks = iter([True, False])

    class _FlakyBackend:
        def is_alive(self, pane_id: str) -> bool:
            return next(checks)

    session = _FakeSession(
        pane_id='%41',
        fake_session_id='session-1',
        ensure_ok=True,
        backend_obj=_FlakyBackend(),
    )
    adapter = ProviderSessionBinding(
        provider='codex',
        load_session=lambda root, instance: session,
        session_id_attr='fake_session_id',
        session_path_attr='fake_session_path',
    )

    monkeypatch.setattr('cli.services.provider_binding._binding_adapter', lambda provider: adapter)
    monkeypatch.setattr('cli.services.provider_binding.time.sleep', lambda delay: None)

    binding = resolve_agent_binding(
        provider='codex',
        agent_name='agent1',
        workspace_path=tmp_path / 'workspace',
        project_root=tmp_path / 'project',
        ensure_usable=True,
    )

    assert binding is None


def test_resolve_agent_binding_preserves_tmux_socket_name_from_session_data(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session = _FakeSession(
        pane_id='%41',
        fake_session_id='session-1',
        ensure_ok=True,
        data={'tmux_socket_name': 'sock-demo'},
    )
    adapter = ProviderSessionBinding(
        provider='codex',
        load_session=lambda root, instance: session,
        session_id_attr='fake_session_id',
        session_path_attr='fake_session_path',
    )

    monkeypatch.setattr('cli.services.provider_binding._binding_adapter', lambda provider: adapter)

    binding = resolve_agent_binding(
        provider='codex',
        agent_name='agent1',
        workspace_path=tmp_path / 'workspace',
        project_root=tmp_path / 'project',
        ensure_usable=False,
    )

    assert binding is not None
    assert binding.tmux_socket_name == 'sock-demo'


def test_resolve_agent_binding_marks_missing_tmux_pane_without_marker_recovery(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class _Backend:
        def pane_exists(self, pane_id: str) -> bool:
            return pane_id != '%41'

        def is_tmux_pane_alive(self, pane_id: str) -> bool:
            return False

    session = _FakeSession(
        pane_id='%41',
        fake_session_id='session-1',
        ensure_ok=True,
        backend_obj=_Backend(),
        data={'tmux_socket_name': 'sock-demo'},
    )
    session.pane_title_marker = 'CCB-agent1-demo'  # type: ignore[attr-defined]
    session.ensure_pane = lambda: (True, '%41')  # type: ignore[method-assign]
    adapter = ProviderSessionBinding(
        provider='codex',
        load_session=lambda root, instance: session,
        session_id_attr='fake_session_id',
        session_path_attr='fake_session_path',
    )

    monkeypatch.setattr('cli.services.provider_binding._binding_adapter', lambda provider: adapter)

    binding = resolve_agent_binding(
        provider='codex',
        agent_name='agent1',
        workspace_path=tmp_path / 'workspace',
        project_root=tmp_path / 'project',
        ensure_usable=False,
    )

    assert binding is not None
    assert binding.tmux_socket_name == 'sock-demo'
    assert binding.runtime_ref == 'tmux:%41'
    assert binding.pane_id == '%41'
    assert binding.active_pane_id is None
    assert binding.pane_title_marker == 'CCB-agent1-demo'
    assert binding.pane_state == 'missing'


def test_resolve_agent_binding_rejects_live_foreign_tmux_pane(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class _Backend:
        def pane_exists(self, pane_id: str) -> bool:
            return True

        def is_tmux_pane_alive(self, pane_id: str) -> bool:
            return True

        def describe_pane(self, pane_id: str, *, user_options: tuple[str, ...] = ()) -> dict[str, str]:
            assert pane_id == '%41'
            return {
                'pane_id': '%41',
                'pane_title': 'OpenCode',
                'pane_dead': '0',
                '@ccb_agent': 'demo',
                '@ccb_project_id': 'foreign-project',
            }

    session = _FakeSession(
        pane_id='%41',
        fake_session_id='session-1',
        ensure_ok=True,
        backend_obj=_Backend(),
        data={
            'agent_name': 'agent1',
            'ccb_project_id': 'current-project',
            'tmux_socket_name': 'sock-demo',
        },
    )
    session.pane_title_marker = 'CCB-agent1-demo'  # type: ignore[attr-defined]
    session.ensure_pane = lambda: (True, '%41')  # type: ignore[method-assign]
    adapter = ProviderSessionBinding(
        provider='codex',
        load_session=lambda root, instance: session,
        session_id_attr='fake_session_id',
        session_path_attr='fake_session_path',
    )

    monkeypatch.setattr('cli.services.provider_binding._binding_adapter', lambda provider: adapter)

    raw_binding = resolve_agent_binding(
        provider='codex',
        agent_name='agent1',
        workspace_path=tmp_path / 'workspace',
        project_root=tmp_path / 'project',
        ensure_usable=False,
    )
    usable_binding = resolve_agent_binding(
        provider='codex',
        agent_name='agent1',
        workspace_path=tmp_path / 'workspace',
        project_root=tmp_path / 'project',
        ensure_usable=True,
    )

    assert raw_binding is not None
    assert raw_binding.pane_state == 'foreign'
    assert raw_binding.active_pane_id is None
    assert usable_binding is None


def test_resolve_agent_binding_surfaces_provider_identity_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session = _FakeSession(pane_id='%41', fake_session_id='session-1', ensure_ok=True)
    adapter = ProviderSessionBinding(
        provider='codex',
        load_session=lambda root, instance: session,
        session_id_attr='fake_session_id',
        session_path_attr='fake_session_path',
        live_runtime_identity=lambda candidate: ProviderRuntimeIdentity(
            'mismatch',
            'live_codex_process_not_running_bound_resume_session',
        ),
    )

    monkeypatch.setattr('cli.services.provider_binding._binding_adapter', lambda provider: adapter)

    binding = resolve_agent_binding(
        provider='codex',
        agent_name='agent1',
        workspace_path=tmp_path / 'workspace',
        project_root=tmp_path / 'project',
        ensure_usable=False,
    )

    assert binding is not None
    assert binding.provider_identity_state == 'mismatch'
    assert binding.provider_identity_reason == 'live_codex_process_not_running_bound_resume_session'


def test_resolve_agent_binding_named_agent_does_not_fallback_to_primary_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    named_session = _FakeSession(
        pane_id='%41',
        fake_session_id='agent3-session',
        ensure_ok=False,
        data={'tmux_socket_name': 'sock-agent3', 'active': True},
    )
    primary_session = _FakeSession(
        pane_id='%74',
        fake_session_id='primary-session',
        ensure_ok=True,
        data={'tmux_socket_name': 'sock-primary', 'active': True},
    )

    def _load_session(root, instance):
        if instance == 'agent3':
            return named_session
        if instance is None:
            return primary_session
        return None

    adapter = ProviderSessionBinding(
        provider='claude',
        load_session=_load_session,
        session_id_attr='fake_session_id',
        session_path_attr='fake_session_path',
    )

    monkeypatch.setattr('cli.services.provider_binding._binding_adapter', lambda provider: adapter)

    binding = resolve_agent_binding(
        provider='claude',
        agent_name='agent3',
        workspace_path=tmp_path / 'workspace',
        project_root=tmp_path / 'project',
        ensure_usable=True,
    )

    assert binding is None
