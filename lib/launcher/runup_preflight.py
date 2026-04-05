from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from typing import Callable

from launcher.runup import LauncherRunUpLayout, plan_two_column_layout


@dataclass(frozen=True)
class LauncherRunUpPreflightResult:
    code: int | None
    terminal_type: str | None
    anchor_name: str | None = None
    anchor_pane_id: str | None = None
    cmd_settings: dict | None = None
    layout: LauncherRunUpLayout | None = None


@dataclass
class LauncherRunUpPreflight:
    target_names: tuple[str, ...]
    terminal_type: str | None
    require_project_config_dir_fn: Callable[[], bool]
    backfill_claude_session_fn: Callable[[], None]
    current_pane_id_fn: Callable[[], str]
    cmd_settings_fn: Callable[[], dict]
    translate_fn: Callable[[str], str]
    stderr: object = sys.stderr

    def prepare(self) -> LauncherRunUpPreflightResult:
        terminal_type = self._resolve_terminal_type(self.terminal_type)
        if terminal_type is None:
            self._print_missing_terminal()
            return LauncherRunUpPreflightResult(code=2, terminal_type=None)

        if not self.require_project_config_dir_fn():
            return LauncherRunUpPreflightResult(code=2, terminal_type=terminal_type)

        self.backfill_claude_session_fn()

        if not self.target_names:
            print(
                '❌ No targets configured. Define target names in .ccb/ccb.config or pass them on the command line.',
                file=self.stderr,
            )
            return LauncherRunUpPreflightResult(code=2, terminal_type=terminal_type)

        anchor_name = self.target_names[-1]
        anchor_pane_id = self.current_pane_id_fn()
        if not anchor_pane_id:
            print('❌ Unable to determine current pane id. Run inside tmux.', file=self.stderr)
            return LauncherRunUpPreflightResult(code=2, terminal_type=terminal_type)

        cmd_settings = self.cmd_settings_fn()
        spawn_items: list[str] = []
        if cmd_settings.get('enabled'):
            spawn_items.append('cmd')
        spawn_items.extend(list(reversed(self.target_names[:-1])))
        layout = plan_two_column_layout(anchor_name=anchor_name, spawn_items=list(spawn_items))
        return LauncherRunUpPreflightResult(
            code=None,
            terminal_type=terminal_type,
            anchor_name=anchor_name,
            anchor_pane_id=anchor_pane_id,
            cmd_settings=cmd_settings,
            layout=layout,
        )

    def _resolve_terminal_type(self, terminal_type: str | None) -> str | None:
        inside_tmux = bool(os.environ.get('TMUX') or os.environ.get('TMUX_PANE'))
        if terminal_type == 'tmux' and not inside_tmux:
            return None
        return terminal_type

    def _print_missing_terminal(self) -> None:
        print(f"❌ {self.translate_fn('no_terminal_backend')}", file=self.stderr)
        print(f"   {self.translate_fn('solutions')}", file=self.stderr)
        print(f"   - {self.translate_fn('install_tmux')}", file=self.stderr)
        if shutil.which('tmux') or shutil.which('tmux.exe'):
            print(f"   - {self.translate_fn('tmux_installed_not_inside')}", file=self.stderr)
