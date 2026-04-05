from __future__ import annotations

import shutil

from i18n import t
from launcher.cleanup import LauncherCleanupCoordinator
from launcher.lifecycle import cleanup_launcher as _cleanup_launcher_wired
from launcher.lifecycle import run_up_launcher as _run_up_launcher_wired
from launcher.maintenance.runtime_maintenance import cleanup_stale_runtime_dirs as _cleanup_stale_runtime_dirs
from launcher.maintenance.runtime_maintenance import cleanup_tmpclaude_artifacts as _cleanup_tmpclaude_artifacts
from launcher.maintenance.runtime_maintenance import get_git_info as _get_git_info
from launcher.maintenance.runtime_maintenance import shrink_ccb_logs as _shrink_ccb_logs
from launcher.runup import LauncherRunUpCoordinator, plan_two_column_layout


def cleanup_app(app, *, kill_panes: bool, clear_sessions: bool, remove_runtime: bool, quiet: bool) -> None:
    _cleanup_launcher_wired(
        app,
        tmux_backend_factory=app._deps.tmux_backend_cls,
        translate_fn=t,
        cleanup_tmpclaude_fn=_cleanup_tmpclaude_artifacts,
        cleanup_stale_runtime_fn=lambda: _cleanup_stale_runtime_dirs(exclude=app.runtime_dir),
        shrink_logs_fn=_shrink_ccb_logs,
        shutil_module=shutil,
        quiet=quiet,
        kill_panes=kill_panes,
        clear_sessions=clear_sessions,
        remove_runtime=remove_runtime,
    )


def run_up_app(app) -> int:
    return _run_up_launcher_wired(
        app,
        version=app._deps.version,
        script_dir=app.script_dir,
        get_git_info_fn=_get_git_info,
        plan_two_column_layout_fn=plan_two_column_layout,
        runup_coordinator_cls=LauncherRunUpCoordinator,
        cleanup_tmpclaude_fn=_cleanup_tmpclaude_artifacts,
        cleanup_stale_runtime_dirs_fn=_cleanup_stale_runtime_dirs,
        shrink_logs_fn=_shrink_ccb_logs,
    )
