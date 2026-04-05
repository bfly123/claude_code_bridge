from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TmuxPaneOwnership:
    state: str
    pane_id: str | None = None
    pane_title: str | None = None
    expected_options: tuple[tuple[str, str], ...] = ()
    actual_options: tuple[tuple[str, str], ...] = ()
    reason: str | None = None

    @property
    def is_owned(self) -> bool:
        return self.state == 'owned'


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


def apply_session_tmux_identity(session, backend, pane_id: str) -> None:
    pane_text = str(pane_id or '').strip()
    if not pane_text:
        return
    pane_title = session_display_title(session)
    title_setter = getattr(backend, 'set_pane_title', None)
    if pane_title and callable(title_setter):
        try:
            title_setter(pane_text, pane_title)
        except Exception:
            pass

    option_setter = getattr(backend, 'set_pane_user_option', None)
    if not callable(option_setter):
        return
    for name, value in session_user_option_lookup(session).items():
        try:
            option_setter(pane_text, name, value)
        except Exception:
            pass


def inspect_tmux_pane_ownership(session, backend, pane_id: str) -> TmuxPaneOwnership:
    pane_text = str(pane_id or '').strip()
    if not pane_text:
        return TmuxPaneOwnership(state='unknown', pane_id=None, reason='pane-id-missing')

    expected = session_user_option_lookup(session)
    expected_items = tuple(sorted(expected.items()))
    if not expected_items:
        return TmuxPaneOwnership(state='owned', pane_id=pane_text, reason='ownership-not-recorded')

    descriptor = getattr(backend, 'describe_pane', None)
    if callable(descriptor):
        try:
            described = descriptor(pane_text, user_options=tuple(name for name, _ in expected_items))
        except Exception:
            described = None
        if isinstance(described, dict):
            actual_title = str(described.get('pane_title') or '').strip() or None
            actual_items = tuple(
                (name, str(described.get(name) or '').strip())
                for name, _ in expected_items
            )
            if all(actual == expected_value for (_, expected_value), (_, actual) in zip(expected_items, actual_items)):
                return TmuxPaneOwnership(
                    state='owned',
                    pane_id=pane_text,
                    pane_title=actual_title,
                    expected_options=expected_items,
                    actual_options=actual_items,
                )
            return TmuxPaneOwnership(
                state='foreign',
                pane_id=pane_text,
                pane_title=actual_title,
                expected_options=expected_items,
                actual_options=actual_items,
                reason='ownership-mismatch',
            )

    lister = getattr(backend, 'list_panes_by_user_options', None)
    if callable(lister):
        try:
            matches = tuple(
                str(item).strip()
                for item in (lister(dict(expected_items)) or ())
                if str(item).strip()
            )
        except Exception:
            matches = ()
        if pane_text in matches:
            return TmuxPaneOwnership(
                state='owned',
                pane_id=pane_text,
                expected_options=expected_items,
                actual_options=expected_items,
            )
        return TmuxPaneOwnership(
            state='foreign',
            pane_id=pane_text,
            expected_options=expected_items,
            actual_options=(),
            reason='ownership-mismatch',
        )

    return TmuxPaneOwnership(
        state='owned',
        pane_id=pane_text,
        expected_options=expected_items,
        actual_options=(),
        reason='inspection-unavailable',
    )


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


def ownership_error_text(ownership: TmuxPaneOwnership, *, pane_id: str | None = None) -> str:
    target = str(pane_id or ownership.pane_id or '').strip() or '<unknown>'
    if ownership.reason == 'ownership-not-recorded':
        return f'Pane ownership not recorded for {target}'
    expected = ', '.join(f'{name}={value}' for name, value in ownership.expected_options) or 'none'
    actual = ', '.join(f'{name}={value}' for name, value in ownership.actual_options) or 'none'
    return (
        f'Pane ownership mismatch for {target}: '
        f'expected [{expected}], actual [{actual}]'
    )


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
    'TmuxPaneOwnership',
    'apply_session_tmux_identity',
    'inspect_tmux_pane_ownership',
    'ownership_error_text',
    'session_display_title',
    'session_pane_title_marker',
    'session_user_option_lookup',
]
