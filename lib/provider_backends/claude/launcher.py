from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import socket
from urllib.parse import urlparse

from agents.models import AgentSpec
from cli.context import CliContext
from cli.models import ParsedStartCommand
from launcher.claude_history import ClaudeHistoryLocator
from provider_backends.claude.session import load_project_session
from provider_backends.runtime_restore import ProviderRestoreTarget, resolve_restore_context
from provider_core.contracts import ProviderRuntimeLauncher
from provider_core.runtime_shared import provider_start_parts
from provider_profiles import ResolvedProviderProfile, load_resolved_provider_profile, provider_api_env_keys
from workspace.models import WorkspacePlan


def build_runtime_launcher() -> ProviderRuntimeLauncher:
    return ProviderRuntimeLauncher(
        provider='claude',
        launch_mode='simple_tmux',
        build_start_cmd=build_start_cmd,
        build_session_payload=build_session_payload,
        resolve_run_cwd=resolve_run_cwd,
    )


def build_start_cmd(command: ParsedStartCommand, spec: AgentSpec, runtime_dir: Path, launch_session_id: str) -> str:
    del launch_session_id
    profile = load_resolved_provider_profile(runtime_dir)
    settings_path = write_claude_settings_overlay(runtime_dir, profile=profile)
    env_prefix = build_claude_env_prefix(profile=profile, extra_env=spec.env)
    restore_target = _resolve_claude_restore_target(spec=spec, runtime_dir=runtime_dir, restore=command.restore)

    cmd_parts = provider_start_parts('claude')
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
    command: ParsedStartCommand,
    spec: AgentSpec,
    plan: WorkspacePlan,
    runtime_dir: Path,
    launch_session_id: str,
) -> Path | str | None:
    del launch_session_id
    return _resolve_claude_restore_target(
        spec=spec,
        runtime_dir=runtime_dir,
        workspace_path=plan.workspace_path,
        restore=command.restore,
    ).run_cwd


def build_session_payload(
    context: CliContext,
    spec: AgentSpec,
    plan: WorkspacePlan,
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


def _resolve_claude_restore_target(
    *,
    spec: AgentSpec,
    runtime_dir: Path,
    restore: bool,
    workspace_path: Path | None = None,
) -> ProviderRestoreTarget:
    context = resolve_restore_context(
        runtime_dir,
        provider='claude',
        agent_name=spec.name,
        workspace_path=workspace_path,
    )
    default_target = ProviderRestoreTarget(run_cwd=context.workspace_path, has_history=False)
    if not restore:
        return default_target

    session_target = _project_session_restore_target(context.workspace_path, context.session_instance)
    if session_target is not None:
        return session_target

    project_root = context.project_root or context.workspace_path
    _session_id, has_history, best_cwd = _claude_history_state(
        invocation_dir=context.workspace_path,
        project_root=project_root,
        include_env_pwd=True,
    )
    if has_history:
        return ProviderRestoreTarget(run_cwd=_existing_dir(best_cwd) or context.workspace_path, has_history=True)
    return default_target


def _project_session_restore_target(workspace_path: Path, session_instance: str | None) -> ProviderRestoreTarget | None:
    session = load_project_session(workspace_path, instance=session_instance)
    if session is None:
        return None
    session_cwd = _existing_dir(getattr(session, 'work_dir', ''))
    if session_cwd is None:
        return None
    _session_id, has_history, best_cwd = _claude_history_state(
        invocation_dir=session_cwd,
        project_root=session_cwd,
        include_env_pwd=False,
    )
    if not has_history:
        return None
    return ProviderRestoreTarget(run_cwd=_existing_dir(best_cwd) or session_cwd, has_history=True)


def _claude_history_state(
    *,
    invocation_dir: Path,
    project_root: Path,
    include_env_pwd: bool,
) -> tuple[str | None, bool, Path | None]:
    locator = ClaudeHistoryLocator(
        invocation_dir=invocation_dir,
        project_root=project_root,
        env=os.environ if include_env_pwd else {},
        home_dir=Path.home(),
    )
    return locator.latest_session_id()


def _existing_dir(value: object) -> Path | None:
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        path = Path(raw).expanduser()
    except Exception:
        return None
    return path if path.is_dir() else None


def write_claude_settings_overlay(
    runtime_dir: Path,
    *,
    profile: ResolvedProviderProfile | None = None,
) -> Path | None:
    del profile
    user_settings_path = Path.home() / '.claude' / 'settings.json'
    try:
        payload = json.loads(user_settings_path.read_text(encoding='utf-8'))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None

    sanitized = {key: value for key, value in payload.items() if key != 'env'}
    if not sanitized:
        return None

    settings_path = runtime_dir / 'claude-settings.json'
    settings_path.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2), encoding='utf-8')
    return settings_path


def build_claude_env_prefix(
    *,
    profile: ResolvedProviderProfile | None = None,
    extra_env: dict[str, str] | None = None,
) -> str:
    api_keys = provider_api_env_keys('claude')
    explicit_env: dict[str, str] = {}
    if profile is not None:
        explicit_env.update({key: value for key, value in profile.env.items() if key in api_keys})
    if extra_env:
        explicit_env.update({key: value for key, value in extra_env.items() if key in api_keys})

    parts: list[str] = []
    if profile is not None and not profile.inherit_api:
        for key in sorted(api_keys):
            parts.append(f'unset {key}')

    base_url = explicit_env.get('ANTHROPIC_BASE_URL')
    if base_url:
        if should_drop_claude_base_url(base_url):
            explicit_env.pop('ANTHROPIC_BASE_URL', None)
            if 'unset ANTHROPIC_BASE_URL' not in parts:
                parts.append('unset ANTHROPIC_BASE_URL')
    elif profile is None or profile.inherit_api:
        env_base_url = str(os.environ.get('ANTHROPIC_BASE_URL') or '').strip()
        if env_base_url:
            if should_drop_claude_base_url(env_base_url):
                if 'unset ANTHROPIC_BASE_URL' not in parts:
                    parts.append('unset ANTHROPIC_BASE_URL')
        else:
            settings_base_url = claude_user_base_url()
            if settings_base_url:
                if should_drop_claude_base_url(settings_base_url):
                    if 'unset ANTHROPIC_BASE_URL' not in parts:
                        parts.append('unset ANTHROPIC_BASE_URL')
                else:
                    explicit_env['ANTHROPIC_BASE_URL'] = settings_base_url

    exports = ' '.join(
        f'{key}={shlex.quote(value)}'
        for key, value in sorted(explicit_env.items())
        if str(value).strip()
    )
    if exports:
        parts.append(f'export {exports}')

    return '; '.join(parts)


def claude_user_base_url() -> str:
    user_settings_path = Path.home() / '.claude' / 'settings.json'
    try:
        payload = json.loads(user_settings_path.read_text(encoding='utf-8'))
    except Exception:
        return ''
    if not isinstance(payload, dict):
        return ''
    env_payload = payload.get('env')
    if not isinstance(env_payload, dict):
        return ''
    return str(env_payload.get('ANTHROPIC_BASE_URL') or '').strip()


def should_drop_claude_base_url(value: str) -> bool:
    parsed = urlparse(str(value or '').strip())
    host = (parsed.hostname or '').strip().lower()
    if host not in {'127.0.0.1', 'localhost', '::1'}:
        return False
    port = parsed.port
    if port is None:
        return False
    return not local_tcp_listener_available(host, port)


def local_tcp_listener_available(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except Exception:
        return False


__all__ = [
    'build_claude_env_prefix',
    'build_runtime_launcher',
    'build_start_cmd',
    'resolve_run_cwd',
    'write_claude_settings_overlay',
]
