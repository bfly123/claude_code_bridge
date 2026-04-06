from __future__ import annotations


def tmux_run(backend, args: list[str]) -> None:
    try:
        backend._tmux_run(args, check=False, capture=True)  # type: ignore[attr-defined]
    except Exception:
        return


def capture_tmux_value(backend, args: list[str]) -> str | None:
    try:
        result = backend._tmux_run(args, check=False, capture=True)  # type: ignore[attr-defined]
    except Exception:
        return None
    if getattr(result, 'returncode', 1) != 0:
        return None
    return ((getattr(result, 'stdout', '') or '').splitlines() or [''])[0].strip() or None


def active_session_pane_id(backend, session_name: str) -> str | None:
    try:
        result = backend._tmux_run(  # type: ignore[attr-defined]
            ['list-panes', '-t', session_name, '-F', '#{?pane_active,#{pane_id},}'],
            check=False,
            capture=True,
        )
    except Exception:
        return None
    if getattr(result, 'returncode', 1) != 0:
        return None
    for line in (getattr(result, 'stdout', '') or '').splitlines():
        pane_id = str(line or '').strip()
        if pane_id:
            return pane_id
    return None


def pane_option_value(backend, pane_id: str, option_name: str) -> str | None:
    return capture_tmux_value(
        backend,
        ['display-message', '-p', '-t', pane_id, f'#{{{option_name}}}'],
    )


__all__ = ['active_session_pane_id', 'capture_tmux_value', 'pane_option_value', 'tmux_run']
