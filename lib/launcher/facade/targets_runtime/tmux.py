from __future__ import annotations


def start_codex_tmux(
    launcher,
    *,
    display_label: str | None = None,
    parent_pane: str | None = None,
    direction: str | None = None,
    start_codex_tmux_fn,
    build_export_path_cmd_fn,
    translate_fn,
) -> str | None:
    return start_codex_tmux_fn(
        launcher,
        display_label=display_label,
        parent_pane=parent_pane,
        direction=direction,
        build_export_path_cmd_fn=build_export_path_cmd_fn,
        translate_fn=translate_fn,
    )


def start_simple_tmux_target(
    launcher,
    provider: str,
    *,
    display_label: str | None = None,
    parent_pane: str | None = None,
    direction: str | None = None,
    start_simple_tmux_target_fn,
    build_export_path_cmd_fn,
    translate_fn,
    start_cmd_fn,
    write_session_fn,
) -> str | None:
    return start_simple_tmux_target_fn(
        launcher,
        provider,
        display_label=display_label,
        parent_pane=parent_pane,
        direction=direction,
        build_export_path_cmd_fn=build_export_path_cmd_fn,
        translate_fn=translate_fn,
        start_cmd_fn=start_cmd_fn,
        write_session_fn=write_session_fn,
    )


def start_cmd_pane(
    launcher,
    *,
    parent_pane: str | None,
    direction: str | None,
    cmd_settings: dict,
    start_cmd_pane_fn,
    build_pane_title_cmd_fn,
    build_export_path_cmd_fn,
    build_cd_cmd_fn,
) -> str | None:
    return start_cmd_pane_fn(
        launcher,
        parent_pane=parent_pane,
        direction=direction,
        cmd_settings=cmd_settings,
        build_pane_title_cmd_fn=build_pane_title_cmd_fn,
        build_export_path_cmd_fn=build_export_path_cmd_fn,
        build_cd_cmd_fn=build_cd_cmd_fn,
    )
