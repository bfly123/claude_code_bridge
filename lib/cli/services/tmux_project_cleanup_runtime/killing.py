from __future__ import annotations

from .backend import build_backend


def kill_panes(
    pane_ids: list[str] | tuple[str, ...],
    *,
    socket_name: str | None,
    backend_factory,
    current_pane_id: str | None,
) -> tuple[str, ...]:
    backend = build_backend(backend_factory, socket_name=socket_name)
    if backend is None:
        return ()

    current_pane = str(current_pane_id or '').strip()
    ordered = [pane for pane in pane_ids if pane != current_pane]
    if current_pane and current_pane in pane_ids:
        ordered.append(current_pane)

    strict_kill = getattr(backend, 'kill_tmux_pane', None)
    legacy_kill = getattr(backend, 'kill_pane', None)

    killed: list[str] = []
    for pane_id in ordered:
        try:
            if callable(strict_kill):
                strict_kill(pane_id)
            elif callable(legacy_kill):
                legacy_kill(pane_id)
            else:
                continue
        except Exception:
            continue
        killed.append(pane_id)
    return tuple(killed)


__all__ = ['kill_panes']
