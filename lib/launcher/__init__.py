"""
Launcher package surface for the current startup/runtime orchestration.

The package exposes stable imports via lazy attribute resolution so the
composition root stays explicit without turning package import into an
eager dependency fan-out.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "LauncherCurrentPaneRouter",
    "LauncherApp",
    "LauncherAppDeps",
    "LauncherFacadeMixin",
    "LauncherProjectMixin",
    "LauncherRuntimeMixin",
    "cleanup_app",
    "run_up_app",
    "init_runtime_state",
    "build_core_services",
    "build_store_services",
    "build_launcher_services",
    "build_runup_services",
    "configure_managed_env",
    "build_claude_env",
    "claude_env_overrides",
    "LauncherClaudePaneLauncher",
    "LauncherCmdPaneLauncher",
    "LauncherCodexCurrentPaneStarter",
    "LauncherClaudeEnvBuilder",
    "ClaudeHistoryLocator",
    "ClaudeStartPlan",
    "LauncherClaudeStartPlanner",
    "LauncherCleanupCoordinator",
    "LauncherCurrentPaneBinder",
    "LauncherCurrentTargetLauncher",
    "LauncherTmuxPaneLauncher",
    "LauncherTargetTmuxStarter",
    "LauncherTargetSessionStore",
    "LauncherTargetRouter",
    "LauncherRunUpCoordinator",
    "LauncherRunUpLayout",
    "LauncherRunUpPreflight",
    "LauncherRunUpPreflightResult",
    "LauncherSessionGateway",
    "LauncherStartCommandFactory",
    "plan_two_column_layout",
    "ClaudeLocalSessionStore",
    "choose_tmux_split_target",
    "label_tmux_pane",
    "mark_session_inactive",
    "read_session_json",
    "spawn_tmux_pane",
    "write_session_json",
    "LauncherWarmupService",
    "start_provider",
]


def __getattr__(name: str) -> Any:
    if name == "LauncherCurrentPaneRouter":
        return getattr(import_module(".current_pane_router", __name__), name)
    if name == "LauncherApp":
        return getattr(import_module(".app", __name__), name)
    if name in {"LauncherAppDeps", "configure_facade_dependencies"}:
        return getattr(import_module(".app_deps", __name__), name)
    if name == "LauncherFacadeMixin":
        return getattr(import_module(".app_facade", __name__), name)
    if name == "LauncherProjectMixin":
        return getattr(import_module(".app_project", __name__), name)
    if name == "LauncherRuntimeMixin":
        return getattr(import_module(".app_runtime", __name__), name)
    if name in {"cleanup_app", "run_up_app"}:
        return getattr(import_module(".app_lifecycle", __name__), name)
    if name in {
        "init_runtime_state",
        "build_core_services",
        "build_store_services",
        "build_launcher_services",
        "build_runup_services",
        "configure_managed_env",
    }:
        return getattr(import_module(".app_wiring", __name__), name)
    if name in {"build_claude_env", "claude_env_overrides"}:
        return getattr(import_module(".app_support", __name__), name)
    if name == "LauncherClaudePaneLauncher":
        return getattr(import_module(".claude_launcher", __name__), name)
    if name == "LauncherCmdPaneLauncher":
        return getattr(import_module(".cmd_pane_launcher", __name__), name)
    if name == "LauncherCodexCurrentPaneStarter":
        return getattr(import_module(".codex_current_launcher", __name__), name)
    if name == "LauncherClaudeEnvBuilder":
        return getattr(import_module(".claude_env", __name__), name)
    if name == "ClaudeHistoryLocator":
        return getattr(import_module(".claude_history", __name__), name)
    if name in {"ClaudeStartPlan", "LauncherClaudeStartPlanner"}:
        return getattr(import_module(".claude_start", __name__), name)
    if name == "LauncherCleanupCoordinator":
        return getattr(import_module(".cleanup", __name__), name)
    if name == "LauncherCurrentPaneBinder":
        return getattr(import_module(".current_pane", __name__), name)
    if name == "LauncherCurrentTargetLauncher":
        return getattr(import_module(".current_target_launcher", __name__), name)
    if name == "LauncherTmuxPaneLauncher":
        return getattr(import_module(".pane_launcher", __name__), name)
    if name == "LauncherTargetTmuxStarter":
        return getattr(import_module(".target_tmux_launcher", __name__), name)
    if name == "LauncherTargetSessionStore":
        return getattr(import_module(".target_session_store", __name__), name)
    if name == "LauncherTargetRouter":
        return getattr(import_module(".target_router", __name__), name)
    if name in {"LauncherRunUpCoordinator", "LauncherRunUpLayout", "plan_two_column_layout"}:
        return getattr(import_module(".runup", __name__), name)
    if name in {"LauncherRunUpPreflight", "LauncherRunUpPreflightResult"}:
        return getattr(import_module(".runup_preflight", __name__), name)
    if name == "LauncherStartCommandFactory":
        return getattr(import_module(".start_commands", __name__), name)
    if name in {
        "ClaudeLocalSessionStore",
        "mark_session_inactive",
        "read_session_json",
        "write_session_json",
    }:
        return getattr(import_module(".session_store", __name__), name)
    if name == "LauncherSessionGateway":
        return getattr(import_module(".session_gateway", __name__), name)
    if name in {"choose_tmux_split_target", "label_tmux_pane", "spawn_tmux_pane"}:
        return getattr(import_module(".tmux_helpers", __name__), name)
    if name == "LauncherWarmupService":
        return getattr(import_module(".warmup", __name__), name)
    if name == "start_provider":
        return getattr(import_module(".app_targets", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
