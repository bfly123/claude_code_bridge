from __future__ import annotations

from .inspection import TmuxPaneOwnership


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


__all__ = ['ownership_error_text']
