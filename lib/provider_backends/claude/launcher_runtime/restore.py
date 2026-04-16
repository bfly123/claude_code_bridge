from __future__ import annotations

import os
from pathlib import Path

from provider_backends.runtime_restore import ProviderRestoreTarget, resolve_restore_context

from .history import ClaudeHistoryLocator


def resolve_claude_restore_target(
    *,
    spec,
    runtime_dir: Path,
    restore: bool,
    workspace_path: Path | None = None,
    project_session_restore_target_fn,
    claude_history_state_fn,
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

    session_target = project_session_restore_target_fn(context.workspace_path, context.session_instance)
    if session_target is not None:
        return session_target

    managed_workspace = is_ccb_managed_workspace(context.workspace_path)
    project_root = context.workspace_path if managed_workspace else (context.project_root or context.workspace_path)
    _session_id, has_history, best_cwd = claude_history_state_fn(
        invocation_dir=context.workspace_path,
        project_root=project_root,
        include_env_pwd=not managed_workspace,
    )
    if has_history:
        return ProviderRestoreTarget(run_cwd=existing_dir(best_cwd) or context.workspace_path, has_history=True)
    return default_target


def project_session_restore_target(
    workspace_path: Path,
    session_instance: str | None,
    *,
    load_project_session_fn,
    claude_history_state_fn,
) -> ProviderRestoreTarget | None:
    session = load_project_session_fn(workspace_path, instance=session_instance)
    if session is None:
        return None
    session_cwd = existing_dir(getattr(session, 'work_dir', ''))
    if session_cwd is None:
        return None
    _session_id, has_history, best_cwd = claude_history_state_fn(
        invocation_dir=session_cwd,
        project_root=session_cwd,
        include_env_pwd=False,
    )
    if not has_history:
        return None
    return ProviderRestoreTarget(run_cwd=existing_dir(best_cwd) or session_cwd, has_history=True)


def claude_history_state(
    *,
    invocation_dir: Path,
    project_root: Path,
    env: dict[str, str] | None = None,
    home_dir: Path,
) -> tuple[str | None, bool, Path | None]:
    locator = ClaudeHistoryLocator(
        invocation_dir=invocation_dir,
        project_root=project_root,
        env=env or {},
        home_dir=home_dir,
    )
    return locator.latest_session_id()


def existing_dir(value: object) -> Path | None:
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        path = Path(raw).expanduser()
    except Exception:
        return None
    return path if path.is_dir() else None


def is_ccb_managed_workspace(workspace_path: Path) -> bool:
    try:
        return (workspace_path / ".ccb-workspace.json").is_file()
    except Exception:
        return False


__all__ = [
    'claude_history_state',
    'existing_dir',
    'is_ccb_managed_workspace',
    'project_session_restore_target',
    'resolve_claude_restore_target',
]
