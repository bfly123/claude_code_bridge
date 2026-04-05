from __future__ import annotations


def start_provider_in_current_pane(
    launcher,
    provider: str,
    *,
    display_label: str | None,
) -> int:
    label = launcher._display_label(provider, display_label)
    return launcher.current_pane_router.start(
        provider,
        display_label=label,
        starters={
            "claude": lambda: launcher._start_claude(display_label=label),
            "codex": lambda: launcher._start_codex_current_pane(display_label=label),
            "gemini": lambda: launcher._start_gemini_current_pane(display_label=label),
            "opencode": lambda: launcher._start_opencode_current_pane(display_label=label),
            "droid": lambda: launcher._start_droid_current_pane(display_label=label),
        },
    )
