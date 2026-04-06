from __future__ import annotations

from .backend import build_backend


def list_project_tmux_panes(
    *,
    project_id: str,
    socket_name: str | None,
    backend_factory,
    tmux_available_fn,
) -> tuple[str, ...]:
    project_text = str(project_id or '').strip()
    if not project_text or tmux_available_fn('tmux') is None:
        return ()

    backend = build_backend(backend_factory, socket_name=socket_name)
    if backend is None:
        return ()

    lister = getattr(backend, 'list_panes_by_user_options', None)
    if not callable(lister):
        return ()

    try:
        pane_ids = [
            str(item).strip()
            for item in lister({'@ccb_project_id': project_text})
            if str(item).strip().startswith('%')
        ]
    except Exception:
        return ()
    if not pane_ids:
        return ()
    return tuple(dict.fromkeys(pane_ids))


__all__ = ['list_project_tmux_panes']
