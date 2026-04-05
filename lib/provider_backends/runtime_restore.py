from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProviderRestoreTarget:
    run_cwd: Path
    has_history: bool


@dataclass(frozen=True)
class ProviderRestoreContext:
    project_root: Path | None
    workspace_path: Path
    session_instance: str | None


def resolve_restore_context(
    runtime_dir: Path,
    *,
    provider: str,
    agent_name: str,
    workspace_path: Path | None = None,
) -> ProviderRestoreContext:
    ccb_dir = _find_ccb_dir(runtime_dir)
    default_workspace = runtime_dir
    if ccb_dir is not None:
        default_workspace = ccb_dir / 'workspaces' / agent_name
    resolved_workspace = Path(workspace_path) if workspace_path is not None else default_workspace

    normalized_provider = str(provider or '').strip().lower()
    normalized_agent = str(agent_name or '').strip()
    session_instance = normalized_agent if normalized_agent and normalized_agent.lower() != normalized_provider else None
    return ProviderRestoreContext(
        project_root=ccb_dir.parent if ccb_dir is not None else None,
        workspace_path=resolved_workspace,
        session_instance=session_instance,
    )


def _find_ccb_dir(start: Path) -> Path | None:
    current = Path(start)
    for parent in (current, *current.parents):
        if parent.name == '.ccb':
            return parent
    return None


__all__ = ['ProviderRestoreContext', 'ProviderRestoreTarget', 'resolve_restore_context']
