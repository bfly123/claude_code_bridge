from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable


@dataclass
class TmuxRespawnService:
    tmux_run_fn: Callable[..., object]
    ensure_pane_log_fn: Callable[[str], object]
    normalize_start_dir_fn: Callable[[str | None], str | None]
    append_stderr_redirection_fn: Callable[[str, str | None], tuple[str, str | None]]
    resolve_shell_fn: Callable[..., str]
    resolve_shell_flags_fn: Callable[..., list[str]]
    build_shell_command_fn: Callable[..., str]
    build_respawn_tmux_args_fn: Callable[..., list[str]]
    default_shell_fn: Callable[[], tuple[str, str]]
    env: dict[str, str]

    def respawn_pane(
        self,
        pane_id: str,
        *,
        cmd: str,
        cwd: str | None = None,
        stderr_log_path: str | None = None,
        remain_on_exit: bool = True,
    ) -> None:
        if not pane_id:
            raise ValueError('pane_id is required')
        try:
            self.ensure_pane_log_fn(pane_id)
        except Exception:
            pass

        cmd_body = (cmd or '').strip()
        if not cmd_body:
            raise ValueError('cmd is required')

        start_dir = self.normalize_start_dir_fn(cwd)
        cmd_body, _ = self.append_stderr_redirection_fn(cmd_body, stderr_log_path)

        tmux_default_shell = ''
        try:
            cp = self.tmux_run_fn(['show-option', '-gqv', 'default-shell'], capture=True, timeout=1.0)
            tmux_default_shell = (getattr(cp, 'stdout', '') or '').strip()
        except Exception:
            tmux_default_shell = ''

        shell = self.resolve_shell_fn(
            env_shell=self.env.get('CCB_TMUX_SHELL', ''),
            tmux_default_shell=tmux_default_shell,
            process_shell=self.env.get('SHELL', ''),
            fallback_shell=self.default_shell_fn()[0],
        )
        flags = self.resolve_shell_flags_fn(
            shell=shell,
            flags_raw=self.env.get('CCB_TMUX_SHELL_FLAGS', ''),
        )
        full = self.build_shell_command_fn(shell=shell, flags=flags, cmd_body=cmd_body)

        if remain_on_exit:
            self.tmux_run_fn(['set-option', '-p', '-t', pane_id, 'remain-on-exit', 'on'], check=False)
        tmux_args = self.build_respawn_tmux_args_fn(
            pane_id=pane_id,
            start_dir=start_dir,
            full_command=full,
        )
        self.tmux_run_fn(tmux_args, check=True)
        if remain_on_exit:
            self.tmux_run_fn(['set-option', '-p', '-t', pane_id, 'remain-on-exit', 'on'], check=False)
