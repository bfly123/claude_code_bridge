from __future__ import annotations

from pathlib import Path

from provider_core.session_binding_evidence import session_terminal

from ..provider_runtime_facts import load_provider_session
from .models import ProviderPaneAssessment
from .tmux import pane_outside_project_namespace, session_backend, tmux_pane_state


def assess_provider_pane(*, runtime, registry, session_bindings, namespace_state_store) -> ProviderPaneAssessment | None:
    if not _is_tmux_runtime(runtime):
        return None
    binding = _resolve_binding(runtime=runtime, registry=registry, session_bindings=session_bindings)
    if binding is None:
        return None
    workspace_path = _workspace_path(runtime)
    if not workspace_path:
        return None
    session = load_provider_session(binding, Path(workspace_path), runtime.agent_name)
    if session is None:
        return _build_assessment(binding=binding, health='session-missing', pane_state='missing')

    terminal = _session_terminal_name(session)
    if terminal != 'tmux':
        return _build_assessment(
            binding=binding,
            session=session,
            terminal=terminal,
            health='healthy',
        )

    pane_state = _tmux_pane_state(
        runtime=runtime,
        session=session,
        namespace_state_store=namespace_state_store,
    )
    return _build_assessment(
        binding=binding,
        session=session,
        terminal=terminal,
        pane_state=pane_state,
        health=health_from_pane_state(pane_state),
    )


def health_from_pane_state(pane_state: str) -> str:
    return {
        'alive': 'healthy',
        'missing': 'pane-missing',
        'foreign': 'pane-foreign',
    }.get(pane_state, 'pane-dead')


def _is_tmux_runtime(runtime) -> bool:
    return str(runtime.runtime_ref or '').strip().startswith('tmux:')


def _resolve_binding(*, runtime, registry, session_bindings):
    spec = registry.spec_for(runtime.agent_name)
    return session_bindings.get(spec.provider)


def _workspace_path(runtime) -> str:
    return str(runtime.workspace_path or '').strip()


def _session_terminal_name(session) -> str | None:
    return str(session_terminal(session) or '').strip().lower() or None


def _tmux_pane_state(*, runtime, session, namespace_state_store) -> str:
    pane_id = str(getattr(session, 'pane_id', '') or '').strip()
    backend = session_backend(session)
    pane_state = tmux_pane_state(session, backend, pane_id)
    if pane_state != 'alive':
        return pane_state
    if pane_outside_project_namespace(
        runtime=runtime,
        namespace_state_store=namespace_state_store,
        backend=backend,
        pane_id=pane_id,
    ):
        return 'foreign'
    return pane_state


def _build_assessment(
    *,
    binding,
    health: str,
    session=None,
    terminal: str | None = None,
    pane_state: str | None = None,
) -> ProviderPaneAssessment:
    return ProviderPaneAssessment(
        binding=binding,
        session=session,
        terminal=terminal,
        pane_state=pane_state,
        health=health,
    )
