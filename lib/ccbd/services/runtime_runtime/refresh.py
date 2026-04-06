from __future__ import annotations

from pathlib import Path

from agents.models import RuntimeBindingSource, normalize_runtime_binding_source

from ..provider_runtime_facts import build_provider_runtime_facts, ensure_provider_pane, load_provider_session


def _workspace_path(runtime) -> str:
    return str(getattr(runtime, 'workspace_path', '') or '').strip()


def _attach_missing_session(*, attach_runtime_fn, agent_name: str, workspace_path: str, runtime) -> object:
    return attach_runtime_fn(
        agent_name=agent_name,
        workspace_path=workspace_path,
        backend_type=runtime.backend_type,
        pid=runtime.pid,
        runtime_ref=runtime.runtime_ref,
        session_ref=runtime.session_ref,
        health='session-missing',
        binding_source=runtime.binding_source,
    )


def _resolve_pane_id(session, *, recover: bool) -> str | None:
    pane_id = str(getattr(session, 'pane_id', '') or '').strip()
    if not recover:
        return pane_id or None
    ok, pane_or_err = ensure_provider_pane(session)
    if not ok:
        return None
    return str(pane_or_err or '').strip() or None


def _attach_healthy_runtime(
    *,
    attach_runtime_fn,
    agent_name: str,
    workspace_path: str,
    runtime,
    provider: str,
    facts,
    active_pane_id: str | None,
) -> object:
    return attach_runtime_fn(
        agent_name=agent_name,
        workspace_path=workspace_path,
        backend_type=runtime.backend_type,
        pid=runtime.pid,
        runtime_ref=facts.runtime_ref or runtime.runtime_ref,
        session_ref=facts.session_ref or runtime.session_ref,
        health='healthy',
        provider=provider,
        runtime_root=facts.runtime_root,
        runtime_pid=facts.runtime_pid,
        terminal_backend=facts.terminal_backend,
        pane_id=facts.pane_id,
        active_pane_id=active_pane_id,
        pane_title_marker=facts.pane_title_marker,
        pane_state=facts.pane_state,
        tmux_socket_name=facts.tmux_socket_name,
        tmux_socket_path=facts.tmux_socket_path,
        session_file=facts.session_file,
        session_id=facts.session_id,
        binding_source=runtime.binding_source,
    )


def refresh_provider_binding(
    *,
    registry,
    session_bindings,
    attach_runtime_fn,
    agent_name: str,
    recover: bool = False,
):
    runtime = registry.get(agent_name)
    if runtime is None:
        return None
    if normalize_runtime_binding_source(runtime.binding_source) is RuntimeBindingSource.EXTERNAL_ATTACH:
        return runtime
    workspace_path = _workspace_path(runtime)
    if not workspace_path:
        return runtime
    spec = registry.spec_for(agent_name)
    binding = session_bindings.get(spec.provider)
    if binding is None:
        return runtime

    session = load_provider_session(binding, Path(workspace_path), agent_name)
    if session is None:
        return _attach_missing_session(
            attach_runtime_fn=attach_runtime_fn,
            agent_name=agent_name,
            workspace_path=workspace_path,
            runtime=runtime,
        )

    pane_id = _resolve_pane_id(session, recover=recover)
    if recover and pane_id is None:
        return runtime
    facts = build_provider_runtime_facts(
        session,
        binding=binding,
        provider=spec.provider,
        pane_id_override=pane_id,
    )
    return _attach_healthy_runtime(
        attach_runtime_fn=attach_runtime_fn,
        agent_name=agent_name,
        workspace_path=workspace_path,
        runtime=runtime,
        provider=spec.provider,
        facts=facts,
        active_pane_id=pane_id,
    )
