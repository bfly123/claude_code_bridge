from __future__ import annotations

import os
from pathlib import Path
import sys


def start_shell_current_target(
    launcher,
    provider: str,
    *,
    display_label: str | None,
    build_pane_title_cmd_fn,
    build_export_path_cmd_fn,
    start_cmd_fn,
    write_session_fn,
) -> int:
    runtime = launcher.runtime_dir / provider
    label = launcher._display_label(provider, display_label)
    pane_title_marker = f"CCB-{label}"
    start_cmd = (
        launcher._build_env_prefix(launcher._provider_env_overrides(provider))
        + build_export_path_cmd_fn(launcher.script_dir / "bin")
        + start_cmd_fn()
    )
    return launcher.current_target_launcher.start_shell_target(
        runtime=runtime,
        pane_title_marker=pane_title_marker,
        agent_label=label,
        display_label=label,
        bind_session_fn=lambda bound_pane_id: write_session_fn(
            runtime,
            None,
            pane_id=bound_pane_id,
            pane_title_marker=pane_title_marker,
            start_cmd=start_cmd,
        ),
        start_cmd=start_cmd,
        run_shell_command_fn=launcher._run_shell_command,
        cwd=str(Path.cwd()),
    )


def start_opencode_current_pane(
    launcher,
    *,
    display_label: str | None,
    build_pane_title_cmd_fn,
    build_export_path_cmd_fn,
    os_module,
    shlex_module,
    subprocess_module,
) -> int:
    runtime = launcher.runtime_dir / "opencode"
    label = launcher._display_label("opencode", display_label)
    pane_title_marker = f"CCB-{label}"
    opencode_cmd = launcher.start_command_factory.build_opencode_start_cmd()
    start_cmd = (
        launcher._build_env_prefix(launcher._provider_env_overrides("opencode"))
        + build_export_path_cmd_fn(launcher.script_dir / "bin")
        + opencode_cmd
    )
    pane_id = launcher.current_target_launcher.bind_target(
        runtime=runtime,
        pane_title_marker=pane_title_marker,
        agent_label=label,
        bind_session_fn=lambda bound_pane_id: launcher.session_gateway.write_opencode_session(
            runtime,
            None,
            pane_id=bound_pane_id,
            pane_title_marker=pane_title_marker,
            start_cmd=start_cmd,
        ),
        display_label=label,
    )
    if not pane_id:
        return 1

    if launcher.terminal_type == "tmux" and os_module.name != "nt":
        env = launcher._with_bin_path_env()
        env.update(launcher._provider_env_overrides("opencode"))
        env["CCB_SESSION_ID"] = launcher.ccb_session_id
        env["OPENCODE_RUNTIME_DIR"] = str(runtime)
        env["OPENCODE_TERMINAL"] = launcher.terminal_type
        env["OPENCODE_TMUX_SESSION"] = pane_id
        try:
            cmd_parts = shlex_module.split(opencode_cmd)
            if not cmd_parts:
                print("❌ Empty OpenCode start command", file=sys.stderr)
                return 1
            exec_raw = (os.environ.get("CCB_OPENCODE_EXEC") or "").strip().lower()
            use_exec = (exec_raw not in {"0", "false", "no", "off"}) and (len(launcher.target_names) == 1)
            if use_exec:
                os_module.execvpe(cmd_parts[0], cmd_parts, env)
            return subprocess_module.run(cmd_parts, env=env, cwd=str(Path.cwd())).returncode
        except Exception as exc:
            print(f"❌ Failed to start OpenCode: {exc}", file=sys.stderr)
            return 1

    return launcher._run_shell_command(start_cmd, cwd=str(Path.cwd()))
