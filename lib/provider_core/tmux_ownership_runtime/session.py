from __future__ import annotations


def session_user_option_lookup(session) -> dict[str, str]:
    resolver = getattr(session, 'user_option_lookup', None)
    if callable(resolver):
        try:
            resolved = resolver()
        except Exception:
            resolved = None
        if isinstance(resolved, dict):
            normalized = _normalize_option_map(resolved)
            if normalized:
                return normalized

    data = getattr(session, 'data', None)
    if not isinstance(data, dict):
        return {}
    lookup: dict[str, str] = {}
    agent_name = str(data.get('agent_name') or '').strip()
    if agent_name:
        lookup['@ccb_agent'] = agent_name
    project_id = str(data.get('ccb_project_id') or '').strip()
    if project_id:
        lookup['@ccb_project_id'] = project_id
    return lookup


def session_pane_title_marker(session) -> str | None:
    text = str(getattr(session, 'pane_title_marker', '') or '').strip()
    if text:
        return text
    data = getattr(session, 'data', None)
    if isinstance(data, dict):
        text = str(data.get('pane_title_marker') or '').strip()
        if text:
            return text
    return None


def session_display_title(session) -> str | None:
    data = getattr(session, 'data', None)
    if isinstance(data, dict):
        agent_name = str(data.get('agent_name') or '').strip()
        if agent_name:
            return agent_name
    lookup = session_user_option_lookup(session)
    agent_name = str(lookup.get('@ccb_agent') or '').strip()
    if agent_name:
        return agent_name
    return session_pane_title_marker(session)


def _normalize_option_map(values: dict[object, object]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_name, raw_value in dict(values or {}).items():
        name = str(raw_name or '').strip()
        value = str(raw_value or '').strip()
        if not name or not value:
            continue
        if not name.startswith('@'):
            name = f'@{name.lstrip("@")}'
        normalized[name] = value
    return normalized


__all__ = [
    'session_display_title',
    'session_pane_title_marker',
    'session_user_option_lookup',
]
