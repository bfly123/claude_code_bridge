from __future__ import annotations

import os
from pathlib import Path
import shlex

from agents.models import AgentSpec
from cli.context import CliContext
from cli.models import ParsedStartCommand
from provider_backends.gemini.comm_runtime.project_hash import project_hash_candidates
from provider_backends.gemini.session import load_project_session
from provider_backends.runtime_restore import ProviderRestoreTarget, resolve_restore_context
from provider_core.contracts import ProviderRuntimeLauncher
from provider_core.runtime_shared import provider_start_parts
from provider_profiles import ResolvedProviderProfile, load_resolved_provider_profile, provider_api_env_keys
from workspace.models import WorkspacePlan


def build_runtime_launcher() -> ProviderRuntimeLauncher:
    return ProviderRuntimeLauncher(
        provider='gemini',
        launch_mode='simple_tmux',
        build_start_cmd=build_start_cmd,
        build_session_payload=build_session_payload,
        resolve_run_cwd=resolve_run_cwd,
    )


def build_start_cmd(command: ParsedStartCommand, spec: AgentSpec, runtime_dir, launch_session_id: str) -> str:
    del launch_session_id
    runtime_dir = Path(runtime_dir)
    profile = load_resolved_provider_profile(runtime_dir)
    restore_target = _resolve_gemini_restore_target(spec=spec, runtime_dir=runtime_dir, restore=command.restore)
    cmd_parts = provider_start_parts('gemini')
    if command.auto_permission:
        cmd_parts.append('--yolo')
    if restore_target.has_history:
        cmd_parts.extend(['--resume', 'latest'])
    cmd_parts.extend(spec.startup_args)
    cmd = ' '.join(shlex.quote(str(part)) for part in cmd_parts)
    env_prefix = build_gemini_env_prefix(profile=profile, extra_env=spec.env)
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
    return _resolve_gemini_restore_target(
        spec=spec,
        runtime_dir=runtime_dir,
        workspace_path=plan.workspace_path,
        restore=command.restore,
    ).run_cwd


def build_session_payload(
    context: CliContext,
    spec: AgentSpec,
    plan: WorkspacePlan,
    runtime_dir,
    run_cwd: Path,
    pane_id: str,
    pane_title_marker: str,
    start_cmd: str,
    launch_session_id: str,
    prepared_state: dict[str, object],
) -> dict[str, object]:
    del prepared_state
    runtime_dir = Path(runtime_dir)
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


def _resolve_gemini_restore_target(
    *,
    spec: AgentSpec,
    runtime_dir: Path,
    restore: bool,
    workspace_path: Path | None = None,
) -> ProviderRestoreTarget:
    context = resolve_restore_context(
        runtime_dir,
        provider='gemini',
        agent_name=spec.name,
        workspace_path=workspace_path,
    )
    default_target = ProviderRestoreTarget(run_cwd=context.workspace_path, has_history=False)
    if not restore:
        return default_target

    session = load_project_session(context.workspace_path, instance=context.session_instance)
    if session is not None:
        session_cwd = _existing_dir(getattr(session, 'work_dir', ''))
        if session_cwd is not None and _gemini_has_history(session_cwd):
            return ProviderRestoreTarget(run_cwd=session_cwd, has_history=True)

    for candidate in _candidate_dirs(context.workspace_path, context.project_root):
        if _gemini_has_history(candidate):
            return ProviderRestoreTarget(run_cwd=candidate, has_history=True)
    return default_target


def _candidate_dirs(workspace_path: Path, project_root: Path | None) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()

    def _add(value: Path | None) -> None:
        if value is None:
            return
        try:
            path = value.expanduser()
        except Exception:
            return
        if path in seen or not path.is_dir():
            return
        seen.add(path)
        candidates.append(path)

    _add(workspace_path)
    _add(project_root)
    env_pwd = str(os.environ.get('PWD') or '').strip()
    if env_pwd:
        _add(Path(env_pwd))
    return candidates


def _gemini_has_history(work_dir: Path) -> bool:
    gemini_root = Path(os.environ.get('GEMINI_ROOT') or (Path.home() / '.gemini' / 'tmp')).expanduser()
    if not gemini_root.is_dir():
        return False
    for project_hash in project_hash_candidates(work_dir, root=gemini_root):
        chats_dir = gemini_root / project_hash / 'chats'
        if chats_dir.is_dir() and any(chats_dir.glob('session-*.json')):
            return True
    return False


def _existing_dir(value: object) -> Path | None:
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        path = Path(raw).expanduser()
    except Exception:
        return None
    return path if path.is_dir() else None


def build_gemini_env_prefix(
    *,
    profile: ResolvedProviderProfile | None = None,
    extra_env: dict[str, str] | None = None,
) -> str:
    api_keys = provider_api_env_keys('gemini')
    explicit_env: dict[str, str] = {}
    if profile is not None:
        explicit_env.update({key: value for key, value in profile.env.items() if key in api_keys})
    if extra_env:
        explicit_env.update({key: value for key, value in extra_env.items() if key in api_keys})

    parts: list[str] = []
    if profile is not None and not profile.inherit_api:
        for key in sorted(api_keys):
            parts.append(f'unset {key}')

    exports = ' '.join(
        f'{key}={shlex.quote(value)}'
        for key, value in sorted(explicit_env.items())
        if str(value).strip()
    )
    if exports:
        parts.append(f'export {exports}')
    return '; '.join(parts)


__all__ = ['build_runtime_launcher', 'build_start_cmd', 'resolve_run_cwd']
