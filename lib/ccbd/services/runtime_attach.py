from __future__ import annotations

from pathlib import Path

from agents.models import AgentRuntime, AgentState, RuntimeBindingSource, normalize_runtime_binding_source


def binding_source_for_attach(
    existing: AgentRuntime | None,
    *,
    explicit: str | RuntimeBindingSource | None,
) -> RuntimeBindingSource:
    if explicit is not None:
        return normalize_runtime_binding_source(explicit)
    if existing is not None:
        return existing.binding_source
    return RuntimeBindingSource.PROVIDER_SESSION


def state_for_attach(existing_state: AgentState | None, next_health: str) -> AgentState:
    if next_health in {'healthy', 'restored'}:
        if existing_state in {AgentState.DEGRADED, AgentState.STOPPED, AgentState.FAILED} or existing_state is None:
            return AgentState.IDLE
        return existing_state
    return AgentState.DEGRADED


def terminal_backend_from_runtime_ref(runtime_ref: str | None) -> str | None:
    text = str(runtime_ref or '').strip()
    if ':' not in text:
        return None
    backend, _sep, _rest = text.partition(':')
    backend = backend.strip()
    return backend or None


def pane_id_from_runtime_ref(runtime_ref: str | None) -> str | None:
    text = str(runtime_ref or '').strip()
    if ':' not in text:
        return None
    _backend, _sep, pane_id = text.partition(':')
    pane_id = pane_id.strip()
    return pane_id or None


def normalized_text(value: str | None) -> str | None:
    text = str(value or '').strip()
    return text or None


def resolve_session_fields(
    existing: AgentRuntime | None,
    *,
    session_ref: str | None,
    session_file: str | None,
    session_id: str | None,
    session_ref_explicit: bool,
    session_file_explicit: bool,
    session_id_explicit: bool,
) -> tuple[str | None, str | None, str | None]:
    normalized_session_file = normalized_text(session_file)
    normalized_session_id = normalized_text(session_id)
    normalized_session_ref = normalized_text(session_ref)
    next_session_file = normalized_session_file if session_file_explicit else (existing.session_file if existing is not None else None)
    next_session_id = normalized_session_id if session_id_explicit else (existing.session_id if existing is not None else None)
    next_session_ref = normalized_session_ref if session_ref_explicit else (existing.session_ref if existing is not None else None)
    if session_ref_explicit and normalized_session_ref is None:
        if not session_file_explicit:
            next_session_file = None
        if not session_id_explicit:
            next_session_id = None
    if next_session_ref is None:
        next_session_ref = next_session_file or next_session_id
    if next_session_file is None and looks_like_path(next_session_ref):
        next_session_file = next_session_ref
    if next_session_id is None and next_session_ref is not None and not looks_like_path(next_session_ref):
        next_session_id = next_session_ref
    return next_session_file, next_session_id, next_session_ref


def looks_like_path(value: str | None) -> bool:
    text = str(value or '').strip()
    return bool(text) and (text.startswith('/') or text.startswith('~') or '/' in text or '\\' in text)


def coerce_pid(value: object) -> int | None:
    text = str(value or '').strip()
    if not text.isdigit():
        return None
    pid = int(text)
    return pid if pid > 0 else None


def read_pid_file(path: Path) -> int | None:
    if not path.is_file():
        return None
    try:
        return coerce_pid(path.read_text(encoding='utf-8'))
    except Exception:
        return None


__all__ = [
    'binding_source_for_attach',
    'coerce_pid',
    'normalized_text',
    'pane_id_from_runtime_ref',
    'read_pid_file',
    'resolve_session_fields',
    'state_for_attach',
    'terminal_backend_from_runtime_ref',
]
