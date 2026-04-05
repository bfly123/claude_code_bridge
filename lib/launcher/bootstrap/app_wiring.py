from __future__ import annotations

import shutil

from i18n import t
from launcher.claude_history import ClaudeHistoryLocator
from launcher.claude_launcher import LauncherClaudePaneLauncher
from launcher.claude_start import LauncherClaudeStartPlanner
from launcher.cleanup import LauncherCleanupCoordinator
from launcher.cmd_pane_launcher import LauncherCmdPaneLauncher
from launcher.codex_current_launcher import LauncherCodexCurrentPaneStarter
from launcher.current_pane import LauncherCurrentPaneBinder
from launcher.current_pane_router import LauncherCurrentPaneRouter
from launcher.current_target_launcher import LauncherCurrentTargetLauncher
from launcher.commands.factory import LauncherStartCommandFactory
from launcher.maintenance.path_support import extract_session_work_dir_norm as _extract_session_work_dir_norm
from launcher.maintenance.path_support import normalize_path_for_match as _normalize_path_for_match
from launcher.maintenance.path_support import normpath_within as _normpath_within
from launcher.maintenance.path_support import work_dir_match_keys as _work_dir_match_keys
from launcher.maintenance.shell_support import build_cd_cmd as _build_cd_cmd
from launcher.maintenance.shell_support import build_export_path_cmd as _build_export_path_cmd
from launcher.maintenance.shell_support import build_pane_title_cmd as _build_pane_title_cmd
from launcher.pane_launcher import LauncherTmuxPaneLauncher
from launcher.runup_preflight import LauncherRunUpPreflight
from launcher.session_gateway import LauncherSessionGateway
from launcher.session.claude_store import ClaudeLocalSessionStore
from launcher.session.io import mark_session_inactive, read_session_json
from launcher.session.target_store import LauncherTargetSessionStore
from launcher.target_router import LauncherTargetRouter
from launcher.target_tmux_launcher import LauncherTargetTmuxStarter
from launcher.tmux_helpers import label_tmux_pane, spawn_tmux_pane
from launcher.warmup import LauncherWarmupService
from launcher.bootstrap.runtime_state import configure_managed_env as _configure_managed_env_wired
from launcher.bootstrap.runtime_state import init_runtime_state as _init_runtime_state_wired
from launcher.bootstrap.service_wiring import build_core_services as _build_core_services_wired
from launcher.bootstrap.service_wiring import build_launcher_services as _build_launcher_services_wired
from launcher.bootstrap.service_wiring import build_runup_services as _build_runup_services_wired
from launcher.bootstrap.service_wiring import build_store_services as _build_store_services_wired
from pane_registry_runtime import upsert_registry
from project_id import compute_ccb_project_id
from provider_sessions.files import check_session_writable, safe_write_session


def init_runtime_state(app) -> None:
    _init_runtime_state_wired(
        app,
        compute_project_id_fn=compute_ccb_project_id,
        time_module=app._deps.time_module,
        tempfile_module=app._deps.tempfile_module,
        getpass_module=app._deps.getpass_module,
        detect_terminal_type_fn=app._detect_terminal_type,
    )


def build_core_services(app) -> None:
    _build_core_services_wired(
        app,
        start_command_factory_cls=LauncherStartCommandFactory,
        normalize_path_for_match_fn=_normalize_path_for_match,
        normpath_within_fn=_normpath_within,
        build_cd_cmd_fn=_build_cd_cmd,
        translate_fn=t,
    )


def build_store_services(app) -> None:
    _build_store_services_wired(
        app,
        claude_local_session_store_cls=ClaudeLocalSessionStore,
        target_session_store_cls=LauncherTargetSessionStore,
        session_gateway_cls=LauncherSessionGateway,
        check_session_writable_fn=check_session_writable,
        safe_write_session_fn=safe_write_session,
        normalize_path_for_match_fn=_normalize_path_for_match,
        extract_session_work_dir_norm_fn=_extract_session_work_dir_norm,
        work_dir_match_keys_fn=_work_dir_match_keys,
        upsert_registry_fn=upsert_registry,
        compute_project_id_fn=compute_ccb_project_id,
        read_session_json_fn=read_session_json,
    )


def build_launcher_services(app) -> None:
    _build_launcher_services_wired(
        app,
        tmux_pane_launcher_cls=LauncherTmuxPaneLauncher,
        target_tmux_starter_cls=LauncherTargetTmuxStarter,
        cmd_pane_launcher_cls=LauncherCmdPaneLauncher,
        current_pane_binder_cls=LauncherCurrentPaneBinder,
        current_pane_router_cls=LauncherCurrentPaneRouter,
        current_target_launcher_cls=LauncherCurrentTargetLauncher,
        codex_current_launcher_cls=LauncherCodexCurrentPaneStarter,
        claude_pane_launcher_cls=LauncherClaudePaneLauncher,
        claude_history_locator_cls=ClaudeHistoryLocator,
        claude_start_planner_cls=LauncherClaudeStartPlanner,
        tmux_backend_factory=app._deps.tmux_backend_cls,
        spawn_tmux_pane_fn=spawn_tmux_pane,
        label_tmux_pane_fn=label_tmux_pane,
        subprocess_module=app._deps.subprocess_module,
        build_pane_title_cmd_fn=_build_pane_title_cmd,
        build_export_path_cmd_fn=_build_export_path_cmd,
        translate_fn=t,
        shutil_module=shutil,
    )


def build_runup_services(app) -> None:
    _build_runup_services_wired(
        app,
        cleanup_coordinator_cls=LauncherCleanupCoordinator,
        target_router_cls=LauncherTargetRouter,
        runup_preflight_cls=LauncherRunUpPreflight,
        warmup_service_cls=LauncherWarmupService,
        mark_session_inactive_fn=mark_session_inactive,
        safe_write_session_fn=safe_write_session,
        translate_fn=t,
        subprocess_module=app._deps.subprocess_module,
    )


def configure_managed_env(app) -> None:
    _configure_managed_env_wired(app)
