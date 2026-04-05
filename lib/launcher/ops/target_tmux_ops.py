from __future__ import annotations

from pathlib import Path


def start_codex_tmux(
    launcher,
    *,
    display_label: str | None,
    parent_pane: str | None,
    direction: str | None,
    build_export_path_cmd_fn,
    translate_fn,
) -> str | None:
    runtime = launcher.runtime_dir / "codex"
    env_overrides = launcher._provider_env_overrides("codex")
    start_cmd = (
        launcher._build_env_prefix(env_overrides)
        + build_export_path_cmd_fn(launcher.script_dir / "bin")
        + launcher.start_command_factory.build_codex_start_cmd()
    )
    label = launcher._display_label("codex", display_label)
    pane_title_marker = f"CCB-{label}"
    pane_id = launcher.tmux_pane_launcher.start_codex(
        runtime=runtime,
        cwd=Path.cwd(),
        start_cmd=start_cmd,
        pane_title_marker=pane_title_marker,
        agent_label=label,
        parent_pane=parent_pane,
        direction=direction,
        write_session_fn=launcher.session_gateway.write_codex_session,
    )

    print(f"✅ {translate_fn('started_backend', provider=label, terminal='tmux pane', pane_id=pane_id)}")
    return pane_id


def start_simple_tmux_target(
    launcher,
    provider: str,
    *,
    display_label: str | None,
    parent_pane: str | None,
    direction: str | None,
    build_export_path_cmd_fn,
    translate_fn,
    start_cmd_fn,
    write_session_fn,
) -> str | None:
    label = launcher._display_label(provider, display_label)
    return launcher.target_tmux_starter.start(
        target_key=provider,
        display_label=label,
        runtime=launcher.runtime_dir / provider,
        cwd=Path.cwd(),
        start_cmd=launcher._build_env_prefix(launcher._provider_env_overrides(provider))
        + build_export_path_cmd_fn(launcher.script_dir / "bin")
        + start_cmd_fn(),
        pane_title_marker=f"CCB-{label}",
        agent_label=label,
        parent_pane=parent_pane,
        direction=direction,
        write_session_fn=write_session_fn,
        started_backend_text=f"✅ {translate_fn('started_backend', provider='{{provider}}', terminal='tmux pane', pane_id='{{pane_id}}')}",
    )


def start_cmd_pane(
    launcher,
    *,
    parent_pane: str | None,
    direction: str | None,
    cmd_settings: dict,
    build_pane_title_cmd_fn,
    build_export_path_cmd_fn,
    build_cd_cmd_fn,
) -> str | None:
    if not cmd_settings.get("enabled"):
        return None
    title = (cmd_settings.get("title") or "CCB-Cmd").strip() or "CCB-Cmd"
    start_cmd = (cmd_settings.get("start_cmd") or "").strip() or launcher._default_cmd_start_cmd()
    full_cmd = (
        build_pane_title_cmd_fn(title)
        + launcher._build_env_prefix(launcher._provider_env_overrides("codex"))
        + build_export_path_cmd_fn(launcher.script_dir / "bin")
        + build_cd_cmd_fn(Path.cwd())
        + start_cmd
    )
    return launcher.cmd_pane_launcher.start(
        title=title,
        full_cmd=full_cmd,
        cwd=str(Path.cwd()),
        parent_pane=parent_pane,
        direction=direction,
    )
