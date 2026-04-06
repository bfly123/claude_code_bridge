from __future__ import annotations

from pathlib import Path
import shlex

from provider_core.contracts import ProviderRuntimeLauncher


def build_runtime_launcher(
    *,
    build_start_cmd_fn,
    build_session_payload_fn,
    resolve_run_cwd_fn,
) -> ProviderRuntimeLauncher:
    return ProviderRuntimeLauncher(
        provider='claude',
        launch_mode='simple_tmux',
        build_start_cmd=build_start_cmd_fn,
        build_session_payload=build_session_payload_fn,
        resolve_run_cwd=resolve_run_cwd_fn,
    )


def build_start_cmd(
    command,
    spec,
    runtime_dir: Path,
    launch_session_id: str,
    *,
    load_profile_fn,
    write_settings_overlay_fn,
    build_env_prefix_fn,
    resolve_restore_target_fn,
    provider_start_parts_fn,
) -> str:
    del launch_session_id
    profile = load_profile_fn(runtime_dir)
    settings_path = write_settings_overlay_fn(runtime_dir, profile=profile)
    env_prefix = build_env_prefix_fn(profile=profile, extra_env=spec.env)
    restore_target = resolve_restore_target_fn(spec=spec, runtime_dir=runtime_dir, restore=command.restore)

    cmd_parts = provider_start_parts_fn('claude')
    cmd_parts.extend(['--setting-sources', 'user,project,local'])
    if settings_path is not None:
        cmd_parts.extend(['--settings', str(settings_path)])
    if command.auto_permission:
        cmd_parts.append('--dangerously-skip-permissions')
    if restore_target.has_history:
        cmd_parts.append('--continue')
    cmd_parts.extend(spec.startup_args)

    cmd = ' '.join(shlex.quote(str(part)) for part in cmd_parts)
    if env_prefix:
        return f'{env_prefix}; {cmd}'
    return cmd


def resolve_run_cwd(
    command,
    spec,
    plan,
    runtime_dir: Path,
    launch_session_id: str,
    *,
    resolve_restore_target_fn,
) -> Path | str | None:
    del launch_session_id
    return resolve_restore_target_fn(
        spec=spec,
        runtime_dir=runtime_dir,
        workspace_path=plan.workspace_path,
        restore=command.restore,
    ).run_cwd


def build_session_payload(
    context,
    spec,
    plan,
    runtime_dir: Path,
    run_cwd: Path,
    pane_id: str,
    pane_title_marker: str,
    start_cmd: str,
    launch_session_id: str,
    prepared_state: dict[str, object],
) -> dict[str, object]:
    del prepared_state
    return {
        'ccb_session_id': launch_session_id,
        'agent_name': spec.name,
        'ccb_project_id': context.project.project_id,
        'runtime_dir': str(runtime_dir),
        'completion_artifact_dir': str(runtime_dir / 'completion'),
        'terminal': 'tmux',
        'tmux_session': pane_id,
        'pane_id': pane_id,
        'pane_title_marker': pane_title_marker,
        'workspace_path': str(plan.workspace_path),
        'work_dir': str(run_cwd),
        'start_dir': str(context.project.project_root),
        'start_cmd': start_cmd,
    }


__all__ = ['build_runtime_launcher', 'build_session_payload', 'build_start_cmd', 'resolve_run_cwd']
