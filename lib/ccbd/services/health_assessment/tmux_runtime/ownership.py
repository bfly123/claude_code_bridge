from __future__ import annotations

from provider_core.tmux_ownership import inspect_tmux_pane_ownership as inspect_tmux_pane_ownership_impl


def inspect_tmux_pane_ownership(session, backend, pane_id: str):
    return inspect_tmux_pane_ownership_impl(session, backend, pane_id)


__all__ = ['inspect_tmux_pane_ownership']
