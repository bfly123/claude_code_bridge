from __future__ import annotations


def should_validate_session(session) -> bool:
    if session_attr_text(session, 'pane_id'):
        return True
    if session_attr_text(session, 'pane_title_marker'):
        return True
    data = getattr(session, 'data', None)
    if not isinstance(data, dict):
        return True
    if data.get('active') is True:
        return True
    return any(data_field_text(data, key) for key in binding_evidence_keys())


def session_attr_text(session, name: str) -> str:
    return str(getattr(session, name, '') or '').strip()


def data_field_text(data: dict[str, object], name: str) -> str:
    return str(data.get(name) or '').strip()


def binding_evidence_keys() -> tuple[str, ...]:
    return ('pane_id', 'tmux_session', 'pane_title_marker', 'runtime_dir', 'start_cmd', 'codex_start_cmd')


def ensured_pane_id(session) -> str | None:
    ensure = getattr(session, 'ensure_pane', None)
    if not callable(ensure):
        return None
    try:
        ok, pane_or_err = ensure()
    except Exception:
        return ''
    if not ok:
        return ''
    return str(pane_or_err or '').strip() or None


def session_liveness_checker(backend):
    checker = getattr(backend, 'is_alive', None)
    if callable(checker):
        return checker
    checker = getattr(backend, 'is_tmux_pane_alive', None)
    if callable(checker):
        return checker
    return None


__all__ = ['ensured_pane_id', 'session_attr_text', 'session_liveness_checker', 'should_validate_session']
