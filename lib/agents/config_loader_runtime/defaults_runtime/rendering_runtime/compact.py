from __future__ import annotations

from agents.models import PermissionMode, ProviderProfileSpec, QueuePolicy, RestoreMode, RuntimeMode, WorkspaceMode


def can_render_compact(config) -> bool:
    if not config.cmd_enabled:
        return False
    return all(is_compact_agent_compatible(config.agents[name]) for name in config.default_agents)


def is_compact_agent_compatible(spec) -> bool:
    return (
        core_agent_defaults_match(spec)
        and spec.provider_profile == ProviderProfileSpec()
        and spec.branch_template is None
        and not spec.labels
        and spec.description is None
        and not spec.watch_paths
    )


def core_agent_defaults_match(spec) -> bool:
    return (
        spec.target == '.'
        and spec.workspace_mode is WorkspaceMode.GIT_WORKTREE
        and spec.workspace_root is None
        and spec.runtime_mode is RuntimeMode.PANE_BACKED
        and spec.restore_default is RestoreMode.AUTO
        and spec.permission_default is PermissionMode.MANUAL
        and spec.queue_policy is QueuePolicy.SERIAL_PER_AGENT
        and not spec.startup_args
        and not spec.env
    )


__all__ = ['can_render_compact', 'core_agent_defaults_match', 'is_compact_agent_compatible']
