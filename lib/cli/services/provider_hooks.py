from __future__ import annotations

from pathlib import Path
import sys

from provider_backends.claude.launcher_runtime import resolve_claude_home_layout
from provider_hooks.settings import build_hook_command, install_workspace_completion_hooks
from provider_profiles import (
    ResolvedProviderProfile,
    load_resolved_provider_profile,
    materialize_provider_profile,
)


def prepare_workspace_provider_hooks(
    *,
    provider: str,
    workspace_path: Path,
    completion_dir: Path,
    agent_name: str,
    home_root: Path | None,
    resolved_profile: ResolvedProviderProfile | None = None,
) -> Path | None:
    normalized = str(provider or '').strip().lower()
    if normalized not in {'claude', 'gemini'}:
        return None
    command = build_hook_command(
        provider=normalized,
        script_path=Path(__file__).resolve().parents[3] / 'bin' / 'ccb-provider-finish-hook',
        python_executable=sys.executable,
        completion_dir=completion_dir,
        agent_name=agent_name,
        workspace_path=workspace_path,
    )
    return install_workspace_completion_hooks(
        provider=normalized,
        workspace_path=workspace_path,
        home_root=home_root,
        command=command,
        resolved_profile=resolved_profile,
    )


def prepare_provider_workspace(
    *,
    layout,
    spec,
    workspace_path: Path,
    completion_dir: Path,
    agent_name: str,
    refresh_profile: bool = False,
) -> ResolvedProviderProfile:
    runtime_dir = layout.agent_provider_runtime_dir(spec.name, spec.provider)
    resolved_profile = (
        materialize_provider_profile(
            layout=layout,
            spec=spec,
            workspace_path=workspace_path,
        )
        if refresh_profile
        else load_resolved_provider_profile(runtime_dir)
    )
    if resolved_profile is None:
        resolved_profile = materialize_provider_profile(
            layout=layout,
            spec=spec,
            workspace_path=workspace_path,
        )
    prepare_workspace_provider_hooks(
        provider=spec.provider,
        workspace_path=workspace_path,
        completion_dir=completion_dir,
        agent_name=agent_name,
        home_root=provider_hook_home_root(
            layout=layout,
            spec=spec,
            runtime_dir=runtime_dir,
            resolved_profile=resolved_profile,
        ),
        resolved_profile=resolved_profile,
    )
    return resolved_profile


def provider_hook_home_root(
    *,
    layout,
    spec,
    runtime_dir: Path,
    resolved_profile: ResolvedProviderProfile | None,
) -> Path | None:
    provider = str(spec.provider or '').strip().lower()
    if provider == 'claude':
        return resolve_claude_home_layout(runtime_dir, resolved_profile).home_root
    if provider == 'gemini':
        return resolve_gemini_home_root(
            layout=layout,
            agent_name=spec.name,
            resolved_profile=resolved_profile,
        )
    return None


def resolve_gemini_home_root(*, layout, agent_name: str, resolved_profile: ResolvedProviderProfile | None) -> Path:
    if resolved_profile is not None and resolved_profile.runtime_home_path is not None:
        return resolved_profile.runtime_home_path
    return layout.agent_provider_state_dir(agent_name, 'gemini') / 'home'


__all__ = [
    'prepare_provider_workspace',
    'prepare_workspace_provider_hooks',
    'provider_hook_home_root',
    'resolve_gemini_home_root',
]
