from __future__ import annotations


def start_shell_current_target(
    launcher,
    provider: str,
    *,
    display_label: str | None = None,
    start_shell_current_target_fn,
    build_pane_title_cmd_fn,
    build_export_path_cmd_fn,
    start_cmd_fn,
    write_session_fn,
) -> int:
    return start_shell_current_target_fn(
        launcher,
        provider,
        display_label=display_label,
        build_pane_title_cmd_fn=build_pane_title_cmd_fn,
        build_export_path_cmd_fn=build_export_path_cmd_fn,
        start_cmd_fn=start_cmd_fn,
        write_session_fn=write_session_fn,
    )


def start_opencode_current_pane(
    launcher,
    *,
    display_label: str | None = None,
    start_opencode_current_pane_fn,
    build_pane_title_cmd_fn,
    build_export_path_cmd_fn,
    os_module,
    shlex_module,
    subprocess_module,
) -> int:
    return start_opencode_current_pane_fn(
        launcher,
        display_label=display_label,
        build_pane_title_cmd_fn=build_pane_title_cmd_fn,
        build_export_path_cmd_fn=build_export_path_cmd_fn,
        os_module=os_module,
        shlex_module=shlex_module,
        subprocess_module=subprocess_module,
    )


def start_provider_in_current_pane(
    launcher,
    provider: str,
    *,
    display_label: str | None = None,
    start_provider_in_current_pane_fn,
) -> int:
    return start_provider_in_current_pane_fn(
        launcher,
        provider,
        display_label=display_label,
    )
