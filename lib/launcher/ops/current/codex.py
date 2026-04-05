from __future__ import annotations

from pathlib import Path


def start_codex_current_pane(
    launcher,
    *,
    display_label: str | None,
) -> int:
    label = launcher._display_label("codex", display_label)
    return launcher.codex_current_launcher.start(
        runtime=launcher.runtime_dir / "codex",
        script_dir=launcher.script_dir,
        ccb_session_id=launcher.ccb_session_id,
        terminal_type=launcher.terminal_type,
        cwd=Path.cwd(),
        display_label=label,
    )
