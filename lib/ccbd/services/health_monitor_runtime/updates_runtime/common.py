from __future__ import annotations

from provider_core.session_binding_evidence import (
    session_file,
    session_id,
    session_job_id,
    session_job_owner_pid,
    session_pane_title_marker,
    session_ref,
    session_runtime_pid,
    session_runtime_root,
    session_runtime_ref,
    session_terminal,
    session_tmux_socket_name,
    session_tmux_socket_path,
)


def runtime_fields_from_facts(runtime, facts) -> dict[str, object]:
    return {
        'runtime_ref': facts.runtime_ref or runtime.runtime_ref,
        'runtime_root': facts.runtime_root or runtime.runtime_root,
        'runtime_pid': facts.runtime_pid if facts.runtime_pid is not None else runtime.runtime_pid,
        'job_id': facts.job_id or getattr(runtime, 'job_id', None),
        'job_owner_pid': facts.job_owner_pid if facts.job_owner_pid is not None else getattr(runtime, 'job_owner_pid', None),
        'terminal_backend': facts.terminal_backend or runtime.terminal_backend,
        'pane_id': facts.pane_id or runtime.pane_id,
        'pane_title_marker': facts.pane_title_marker or runtime.pane_title_marker,
        'tmux_socket_name': facts.tmux_socket_name or runtime.tmux_socket_name,
        'tmux_socket_path': facts.tmux_socket_path or runtime.tmux_socket_path,
        'session_file': facts.session_file or runtime.session_file,
        'session_id': facts.session_id or runtime.session_id,
    }


def runtime_fields_from_session(runtime, session, binding=None) -> dict[str, object]:
    next_runtime_ref = runtime.runtime_ref
    bound_runtime_ref = session_runtime_ref(session)
    if bound_runtime_ref:
        next_runtime_ref = bound_runtime_ref
    provider_name = str(
        getattr(runtime, 'provider', None) or getattr(binding, 'provider', None) or ''
    ).strip()
    pane_id = str(getattr(session, 'pane_id', '') or '').strip() or runtime.pane_id
    terminal = str(session_terminal(session) or '').strip() or runtime.terminal_backend
    pane_title = str(session_pane_title_marker(session) or '').strip() or runtime.pane_title_marker
    bound_session_id = (
        session_id(session, session_id_attr=binding.session_id_attr)
        if binding is not None and hasattr(binding, 'session_id_attr')
        else None
    )
    return {
        'runtime_ref': next_runtime_ref,
        'runtime_root': session_runtime_root(session) or runtime.runtime_root,
        'runtime_pid': (
            session_runtime_pid(session, provider=provider_name) if provider_name else None
        ) or runtime.runtime_pid,
        'job_id': session_job_id(session) or getattr(runtime, 'job_id', None),
        'job_owner_pid': session_job_owner_pid(session) or getattr(runtime, 'job_owner_pid', None),
        'terminal_backend': terminal,
        'pane_id': pane_id,
        'pane_title_marker': pane_title,
        'tmux_socket_name': session_tmux_socket_name(session) or runtime.tmux_socket_name,
        'tmux_socket_path': session_tmux_socket_path(session) or runtime.tmux_socket_path,
        'session_file': session_file(session) or runtime.session_file,
        'session_id': bound_session_id or runtime.session_id,
    }


def drop_explicit_runtime_fields(
    fields: dict[str, object],
    *,
    explicit_fields: tuple[str, ...],
) -> dict[str, object]:
    cleaned = dict(fields)
    for name in explicit_fields:
        cleaned.pop(name, None)
    return cleaned


def pane_state_for_health(
    runtime,
    health: str,
    *,
    pane_id: str | None = None,
) -> tuple[str | None, str | None]:
    next_pane_state = runtime.pane_state
    next_active_pane_id = runtime.active_pane_id or pane_id or runtime.pane_id
    if health in {'pane-dead', 'orphaned'}:
        next_pane_state = 'dead'
    elif health in {'pane-missing', 'session-missing'}:
        next_pane_state = 'missing'
    elif health == 'pane-foreign':
        next_pane_state = 'foreign'
        next_active_pane_id = None
    return next_pane_state, next_active_pane_id

__all__ = [
    'drop_explicit_runtime_fields',
    'pane_state_for_health',
    'runtime_fields_from_facts',
    'runtime_fields_from_session',
]
