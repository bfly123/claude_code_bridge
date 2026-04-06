from __future__ import annotations

from dataclasses import dataclass

from .session import session_user_option_lookup


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


def inspect_tmux_pane_ownership(session, backend, pane_id: str) -> TmuxPaneOwnership:
    pane_text = str(pane_id or '').strip()
    if not pane_text:
        return TmuxPaneOwnership(state='unknown', pane_id=None, reason='pane-id-missing')

    expected_items = expected_option_items(session)
    if not expected_items:
        return TmuxPaneOwnership(state='owned', pane_id=pane_text, reason='ownership-not-recorded')

    ownership = inspect_described_pane(backend, pane_text, expected_items)
    if ownership is not None:
        return ownership

    ownership = inspect_listed_panes(backend, pane_text, expected_items)
    if ownership is not None:
        return ownership

    return TmuxPaneOwnership(
        state='owned',
        pane_id=pane_text,
        expected_options=expected_items,
        actual_options=(),
        reason='inspection-unavailable',
    )


def expected_option_items(session) -> tuple[tuple[str, str], ...]:
    expected = session_user_option_lookup(session)
    return tuple(sorted(expected.items()))


def inspect_described_pane(
    backend,
    pane_id: str,
    expected_items: tuple[tuple[str, str], ...],
) -> TmuxPaneOwnership | None:
    described = describe_pane(backend, pane_id, expected_items)
    if not isinstance(described, dict):
        return None
    actual_title = str(described.get('pane_title') or '').strip() or None
    actual_items = tuple(
        (name, str(described.get(name) or '').strip())
        for name, _ in expected_items
    )
    if options_match(expected_items, actual_items):
        return TmuxPaneOwnership(
            state='owned',
            pane_id=pane_id,
            pane_title=actual_title,
            expected_options=expected_items,
            actual_options=actual_items,
        )
    return TmuxPaneOwnership(
        state='foreign',
        pane_id=pane_id,
        pane_title=actual_title,
        expected_options=expected_items,
        actual_options=actual_items,
        reason='ownership-mismatch',
    )


def describe_pane(
    backend,
    pane_id: str,
    expected_items: tuple[tuple[str, str], ...],
):
    descriptor = getattr(backend, 'describe_pane', None)
    if not callable(descriptor):
        return None
    try:
        return descriptor(pane_id, user_options=tuple(name for name, _ in expected_items))
    except Exception:
        return None


def inspect_listed_panes(
    backend,
    pane_id: str,
    expected_items: tuple[tuple[str, str], ...],
) -> TmuxPaneOwnership | None:
    matches = listed_pane_matches(backend, expected_items)
    if matches is None:
        return None
    if pane_id in matches:
        return TmuxPaneOwnership(
            state='owned',
            pane_id=pane_id,
            expected_options=expected_items,
            actual_options=expected_items,
        )
    return TmuxPaneOwnership(
        state='foreign',
        pane_id=pane_id,
        expected_options=expected_items,
        actual_options=(),
        reason='ownership-mismatch',
    )


def listed_pane_matches(
    backend,
    expected_items: tuple[tuple[str, str], ...],
) -> tuple[str, ...] | None:
    lister = getattr(backend, 'list_panes_by_user_options', None)
    if not callable(lister):
        return None
    try:
        return tuple(
            str(item).strip()
            for item in (lister(dict(expected_items)) or ())
            if str(item).strip()
        )
    except Exception:
        return ()


def options_match(
    expected_items: tuple[tuple[str, str], ...],
    actual_items: tuple[tuple[str, str], ...],
) -> bool:
    return all(actual == expected_value for (_, expected_value), (_, actual) in zip(expected_items, actual_items))


__all__ = ['TmuxPaneOwnership', 'inspect_tmux_pane_ownership']
