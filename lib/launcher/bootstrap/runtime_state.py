from __future__ import annotations

import os
from pathlib import Path


def init_runtime_state(
    launcher,
    *,
    compute_project_id_fn,
    time_module,
    tempfile_module,
    getpass_module,
    detect_terminal_type_fn,
) -> None:
    try:
        launcher.project_root = launcher.invocation_dir.resolve()
    except Exception:
        launcher.project_root = launcher.invocation_dir.absolute()
    launcher.ccb_session_id = f"ai-{int(time_module.time())}-{os.getpid()}"
    launcher.ccb_pid = os.getpid()
    launcher.project_id = compute_project_id_fn(launcher.project_root)
    project_hash = (launcher.project_id or "")[:16] or "unknown"
    launcher.project_run_dir = Path.home() / ".cache" / "ccb" / "projects" / project_hash
    launcher.temp_base = Path(tempfile_module.gettempdir())
    launcher.runtime_dir = launcher.temp_base / f"claude-ai-{getpass_module.getuser()}" / launcher.ccb_session_id
    launcher.runtime_dir.mkdir(parents=True, exist_ok=True)
    launcher._cleaned = False
    launcher.terminal_type = detect_terminal_type_fn()
    launcher.tmux_sessions = {}
    launcher.tmux_panes = {}
    launcher.extra_panes = {}
    launcher.processes = {}
    launcher.anchor_name = None
    launcher.anchor_pane_id = None


def configure_managed_env(launcher) -> None:
    os.environ["CCB_MANAGED"] = "1"
    os.environ["CCB_PARENT_PID"] = str(launcher.ccb_pid)
    os.environ.setdefault("CCB_RUN_DIR", str(launcher.project_run_dir))
