from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from typing import Callable, TextIO


@dataclass
class LauncherTargetRouter:
    terminal_type: str | None
    target_tmux_starters: dict[str, Callable[..., str | None]]
    translate_fn: Callable[[str], str]
    stderr: TextIO = sys.stderr

    def start(
        self,
        provider: str,
        *,
        display_label: str | None = None,
        parent_pane: str | None = None,
        direction: str | None = None,
    ) -> str | None:
        label = str(display_label or provider).strip() or str(provider)
        if self.terminal_type is None:
            self._print_missing_terminal()
            return None

        if not shutil.which('tmux'):
            print(f"❌ {self.translate_fn('tmux_not_installed')}")
            print(f"   {self.translate_fn('install_tmux')}")
            return None

        if not (os.environ.get('TMUX') or os.environ.get('TMUX_PANE')):
            print(f"❌ {self.translate_fn('tmux_installed_not_inside')}", file=self.stderr)
            print("💡 Run: tmux", file=self.stderr)
            print(f"   Then: {' '.join(['ccb', *sys.argv[1:]])}", file=self.stderr)
            return None

        print(f"🚀 {self.translate_fn('starting_backend', provider=label, terminal='tmux')}")
        starter = self.target_tmux_starters.get((provider or '').strip().lower())
        if starter is None:
            print(f"❌ {self.translate_fn('unknown_provider', provider=provider)}")
            return None
        return starter(parent_pane=parent_pane, direction=direction)

    def _print_missing_terminal(self) -> None:
        print(f"❌ {self.translate_fn('no_terminal_backend')}")
        print(f"   {self.translate_fn('solutions')}")
        print(f"   - {self.translate_fn('install_tmux')}")
        if (shutil.which('tmux') or shutil.which('tmux.exe')) and not (os.environ.get('TMUX') or os.environ.get('TMUX_PANE')):
            print(f"   - {self.translate_fn('tmux_installed_not_inside')}")
