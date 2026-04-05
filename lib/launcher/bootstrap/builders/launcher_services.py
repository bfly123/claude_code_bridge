from __future__ import annotations

import os
from pathlib import Path
import sys


def build_launcher_services(
    launcher,
    *,
    tmux_pane_launcher_cls,
    target_tmux_starter_cls,
    cmd_pane_launcher_cls,
    current_pane_binder_cls,
    current_pane_router_cls,
    current_target_launcher_cls,
    codex_current_launcher_cls,
    claude_pane_launcher_cls,
    claude_history_locator_cls,
    claude_start_planner_cls,
    tmux_backend_factory,
    spawn_tmux_pane_fn,
    label_tmux_pane_fn,
    subprocess_module,
    build_pane_title_cmd_fn,
    build_export_path_cmd_fn,
    translate_fn,
    shutil_module,
) -> None:
    launcher.tmux_pane_launcher = tmux_pane_launcher_cls(
        script_dir=launcher.script_dir,
        tmux_panes=launcher.tmux_panes,
        backend_factory=tmux_backend_factory,
        spawn_tmux_pane_fn=spawn_tmux_pane_fn,
        subprocess_run_fn=subprocess_module.run,
        subprocess_popen_fn=subprocess_module.Popen,
    )
    launcher.target_tmux_starter = target_tmux_starter_cls(
        start_simple_target_fn=launcher.tmux_pane_launcher.start_simple_target,
    )
    launcher.cmd_pane_launcher = cmd_pane_launcher_cls(
        extra_panes=launcher.extra_panes,
        backend_factory=tmux_backend_factory,
        label_tmux_pane_fn=label_tmux_pane_fn,
    )
    launcher.current_pane_binder = current_pane_binder_cls(
        terminal_type=launcher.terminal_type,
        current_pane_id_fn=launcher._current_pane_id,
        backend_factory=tmux_backend_factory,
        label_tmux_pane_fn=label_tmux_pane_fn,
    )
    launcher.current_pane_router = current_pane_router_cls(translate_fn=translate_fn)
    launcher.current_target_launcher = current_target_launcher_cls(
        bind_current_pane_fn=launcher.current_pane_binder.bind,
        stderr=sys.stderr,
    )
    launcher.codex_current_launcher = codex_current_launcher_cls(
        bind_target_fn=launcher.current_target_launcher.bind_target,
        with_bin_path_env_fn=launcher._with_bin_path_env,
        provider_env_overrides_fn=launcher._provider_env_overrides,
        run_shell_command_fn=launcher._run_shell_command,
        build_pane_title_cmd_fn=build_pane_title_cmd_fn,
        build_env_prefix_fn=launcher._build_env_prefix,
        export_path_builder_fn=build_export_path_cmd_fn,
        build_codex_start_cmd_fn=launcher.start_command_factory.build_codex_start_cmd,
        write_codex_session_fn=launcher.session_gateway.write_codex_session,
        popen_fn=subprocess_module.Popen,
        mkfifo_fn=os.mkfifo,
        stderr=sys.stderr,
    )
    launcher.claude_pane_launcher = claude_pane_launcher_cls(
        script_dir=launcher.script_dir,
        tmux_panes=launcher.tmux_panes,
        build_env_prefix_fn=launcher._build_env_prefix,
        export_path_builder_fn=build_export_path_cmd_fn,
        pane_title_builder_fn=build_pane_title_cmd_fn,
        tmux_backend_factory=tmux_backend_factory,
        label_tmux_pane_fn=label_tmux_pane_fn,
    )
    launcher.claude_history_locator = claude_history_locator_cls(
        invocation_dir=launcher.invocation_dir,
        project_root=launcher.project_root,
        env=os.environ,
        home_dir=Path.home(),
    )
    launcher.claude_start_planner = claude_start_planner_cls(
        auto=launcher.auto,
        resume=launcher.resume,
        project_root=launcher.project_root,
        invocation_dir=launcher.invocation_dir,
        platform_name=sys.platform,
        env=os.environ,
        which_fn=shutil_module.which,
        get_latest_session_fn=launcher.claude_history_locator.latest_session_id,
    )
