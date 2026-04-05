from __future__ import annotations


def start_provider(
    launcher,
    provider: str,
    *,
    display_label: str | None = None,
    parent_pane: str | None = None,
    direction: str | None = None,
) -> str | None:
    launcher._sync_terminal_type_state()
    pane_id = launcher.target_router.start(
        provider,
        display_label=launcher._display_label(provider, display_label),
        parent_pane=parent_pane,
        direction=direction,
    )
    launcher.terminal_type = launcher.target_router.terminal_type
    return pane_id
