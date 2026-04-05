from __future__ import annotations

from pathlib import Path
import shutil

from launcher.runtime_helpers import build_env_prefix as _build_env_prefix_wired
from launcher.runtime_helpers import current_pane_id as _current_pane_id_wired
from launcher.runtime_helpers import provider_pane_id as _provider_pane_id_wired
from launcher.runtime_helpers import run_shell_command as _run_shell_command_wired
from launcher.runtime_helpers import set_current_pane_label as _set_current_pane_label_wired
from launcher.runtime_helpers import with_bin_path_env as _with_bin_path_env_wired
from launcher.ops.current.codex import start_codex_current_pane as _start_codex_current_pane_wired
from launcher.tmux_helpers import label_tmux_pane
from launcher.ui_helpers import set_tmux_ui_active as _set_tmux_ui_active_wired
from terminal_runtime import get_shell_type


class LauncherRuntimeMixin:
    def _with_bin_path_env(self, env: dict | None = None) -> dict:
        return _with_bin_path_env_wired(self, env)

    def _current_pane_id(self) -> str:
        return _current_pane_id_wired(
            self,
            tmux_backend_factory=self._deps.tmux_backend_cls,
        )

    def _build_env_prefix(self, env: dict) -> str:
        return _build_env_prefix_wired(
            env,
            get_shell_type_fn=get_shell_type,
            shlex_module=self._deps.shlex_module,
        )

    def _provider_pane_id(self, provider: str) -> str:
        return _provider_pane_id_wired(self, provider)

    def _set_current_pane_label(self, label: str) -> None:
        _set_current_pane_label_wired(
            self,
            label,
            tmux_backend_factory=self._deps.tmux_backend_cls,
            label_tmux_pane_fn=label_tmux_pane,
        )

    def _run_shell_command(self, cmd: str, *, env: dict | None = None, cwd: str | None = None) -> int:
        return _run_shell_command_wired(
            self,
            cmd,
            env=env,
            cwd=cwd,
            get_shell_type_fn=get_shell_type,
            shutil_module=shutil,
            subprocess_module=self._deps.subprocess_module,
        )

    def _set_tmux_ui_active(self, active: bool) -> None:
        _set_tmux_ui_active_wired(
            self,
            active,
            subprocess_module=self._deps.subprocess_module,
        )

    def _backfill_claude_session_work_dir_fields(self) -> None:
        self.claude_session_store.backfill_work_dir_fields()

    def _read_local_claude_session_id(self) -> str | None:
        return self.claude_session_store.read_local_session_id(current_work_dir=Path.cwd())

    def _write_local_claude_session(
        self,
        session_id: str | None = None,
        *,
        active: bool = True,
        pane_id: str | None = None,
        pane_title_marker: str | None = None,
        terminal: str | None = None,
    ) -> None:
        self.claude_session_store.write_local_session(
            session_id=session_id,
            active=active,
            pane_id=pane_id,
            pane_title_marker=pane_title_marker,
            terminal=terminal,
        )

    def _start_codex_current_pane(self, *, display_label: str | None = None) -> int:
        return _start_codex_current_pane_wired(self, display_label=display_label)

    def cleanup(
        self,
        *,
        kill_panes: bool = True,
        clear_sessions: bool = True,
        remove_runtime: bool = True,
        quiet: bool = False,
    ):
        from launcher.bootstrap.app_lifecycle import cleanup_app as _cleanup_app_impl

        _cleanup_app_impl(
            self,
            kill_panes=kill_panes,
            clear_sessions=clear_sessions,
            remove_runtime=remove_runtime,
            quiet=quiet,
        )

    def run_up(self) -> int:
        from launcher.bootstrap.app_lifecycle import run_up_app as _run_up_app_impl

        return _run_up_app_impl(self)
