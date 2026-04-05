from __future__ import annotations


def start_claude(
    launcher,
    *,
    display_label: str | None = None,
    start_claude_fn,
    translate_fn,
    subprocess_module,
) -> int:
    return start_claude_fn(
        launcher,
        display_label=display_label,
        translate_fn=translate_fn,
        subprocess_module=subprocess_module,
    )


def start_claude_pane(
    launcher,
    *,
    parent_pane: str | None,
    direction: str | None,
    display_label: str | None = None,
    start_claude_pane_fn,
    translate_fn,
) -> str | None:
    return start_claude_pane_fn(
        launcher,
        parent_pane=parent_pane,
        direction=direction,
        display_label=display_label,
        translate_fn=translate_fn,
    )
