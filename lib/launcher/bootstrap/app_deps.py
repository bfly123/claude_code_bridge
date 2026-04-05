from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

from i18n import t
from launcher.claude_env import LauncherClaudeEnvBuilder
from launcher.maintenance.shell_support import build_cd_cmd as _build_cd_cmd
from launcher.maintenance.shell_support import build_export_path_cmd as _build_export_path_cmd
from launcher.maintenance.shell_support import build_keep_open_cmd as _build_keep_open_cmd
from launcher.maintenance.shell_support import build_pane_title_cmd as _build_pane_title_cmd
from launcher.ops.current.router import start_provider_in_current_pane as _start_provider_in_current_pane_wired
from launcher.ops.current.shell import start_opencode_current_pane as _start_opencode_current_pane_wired
from launcher.ops.current.shell import start_shell_current_target as _start_shell_current_target_wired
from launcher.ops.target_claude_ops import start_claude as _start_claude_wired
from launcher.ops.target_claude_ops import start_claude_pane as _start_claude_pane_wired
from launcher.ops.target_tmux_ops import start_cmd_pane as _start_cmd_pane_wired
from launcher.ops.target_tmux_ops import start_codex_tmux as _start_codex_tmux_wired
from launcher.ops.target_tmux_ops import start_simple_tmux_target as _start_simple_tmux_target_wired


@dataclass(frozen=True)
class LauncherAppDeps:
    script_dir: Path
    version: str
    supported_client_specs: dict
    tmux_backend_cls: object
    detect_terminal_fn: object
    os_module: object
    subprocess_module: object
    tempfile_module: object
    time_module: object
    getpass_module: object
    shlex_module: object


def configure_facade_dependencies(app, deps: LauncherAppDeps) -> None:
    app._facade_build_cd_cmd_fn = _build_cd_cmd
    app._facade_build_export_path_cmd_fn = _build_export_path_cmd
    app._facade_build_keep_open_cmd_fn = _build_keep_open_cmd
    app._facade_build_pane_title_cmd_fn = _build_pane_title_cmd
    app._facade_claude_env_builder_cls = LauncherClaudeEnvBuilder
    app._facade_environ = deps.os_module.environ
    app._facade_os_module = deps.os_module
    app._facade_shlex_module = deps.shlex_module
    app._facade_start_claude_fn = _start_claude_wired
    app._facade_start_claude_pane_fn = _start_claude_pane_wired
    app._facade_start_cmd_pane_fn = _start_cmd_pane_wired
    app._facade_start_codex_tmux_fn = _start_codex_tmux_wired
    app._facade_start_opencode_current_pane_fn = _start_opencode_current_pane_wired
    app._facade_start_provider_in_current_pane_fn = _start_provider_in_current_pane_wired
    app._facade_start_shell_current_target_fn = _start_shell_current_target_wired
    app._facade_start_simple_tmux_target_fn = _start_simple_tmux_target_wired
    app._facade_stderr = sys.stderr
    app._facade_subprocess_module = deps.subprocess_module
    app._facade_translate_fn = t
    app._deps = deps
