from __future__ import annotations

from pathlib import Path

from provider_profiles import ResolvedProviderProfile

from .claude import install_claude_hooks, trust_claude_workspace
from .gemini import install_gemini_hooks, trust_gemini_workspace


def install_workspace_completion_hooks(
    *,
    provider: str,
    workspace_path: Path,
    home_root: Path | None,
    command: str,
    resolved_profile: ResolvedProviderProfile | None = None,
) -> Path | None:
    normalized = str(provider or '').strip().lower()
    del resolved_profile
    if home_root is None:
        return None
    if normalized == 'claude':
        settings_path = install_claude_hooks(home_root=home_root, command=command)
        trust_claude_workspace(home_root=home_root, workspace_path=workspace_path)
        return settings_path
    if normalized == 'gemini':
        settings_path = install_gemini_hooks(home_root=home_root, command=command)
        trust_gemini_workspace(home_root=home_root, workspace_path=workspace_path)
        return settings_path
    return None


__all__ = ['install_workspace_completion_hooks']
