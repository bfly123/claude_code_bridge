from __future__ import annotations

from pathlib import Path

from provider_profiles import ResolvedProviderProfile

from .claude import install_claude_hooks, sync_claude_workspace_settings, trust_claude_workspace
from .gemini import install_gemini_hooks, trust_gemini_workspace


def install_workspace_completion_hooks(
    *,
    provider: str,
    workspace_path: Path,
    command: str,
    resolved_profile: ResolvedProviderProfile | None = None,
) -> Path | None:
    normalized = str(provider or '').strip().lower()
    if normalized == 'claude':
        settings_path = install_claude_hooks(workspace_path=workspace_path, command=command)
        sync_claude_workspace_settings(workspace_path=workspace_path, resolved_profile=resolved_profile)
        trust_claude_workspace(workspace_path=workspace_path)
        return settings_path
    if normalized == 'gemini':
        settings_path = install_gemini_hooks(workspace_path=workspace_path, command=command)
        trust_gemini_workspace(workspace_path=workspace_path)
        return settings_path
    return None


__all__ = ['install_workspace_completion_hooks']
