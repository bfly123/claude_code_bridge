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
        cmd_body = _required_cmd_body(pane_id, cmd)
        _safe_ensure_pane_log(self, pane_id)
        start_dir = self.normalize_start_dir_fn(cwd)
        cmd_body, _ = self.append_stderr_redirection_fn(cmd_body, stderr_log_path)
        full = _resolved_shell_command(self, cmd_body)
        if remain_on_exit:
            _set_remain_on_exit(self, pane_id)
        tmux_args = self.build_respawn_tmux_args_fn(
            pane_id=pane_id,
            start_dir=start_dir,
            full_command=full,
        )
        self.tmux_run_fn(tmux_args, check=True)
        if remain_on_exit:
            _set_remain_on_exit(self, pane_id)


def _required_cmd_body(pane_id: str, cmd: str) -> str:
    pane_text = str(pane_id or '').strip()
    if not pane_text:
        raise ValueError('pane_id is required')
    cmd_body = (cmd or '').strip()
    if not cmd_body:
        raise ValueError('cmd is required')
    return cmd_body


def _safe_ensure_pane_log(service: TmuxRespawnService, pane_id: str) -> None:
    try:
        service.ensure_pane_log_fn(pane_id)
    except Exception:
        pass


def _resolved_shell_command(service: TmuxRespawnService, cmd_body: str) -> str:
    shell = service.resolve_shell_fn(
        env_shell=service.env.get('CCB_TMUX_SHELL', ''),
        tmux_default_shell=_tmux_default_shell(service),
        process_shell=service.env.get('SHELL', ''),
        fallback_shell=service.default_shell_fn()[0],
    )
    flags = service.resolve_shell_flags_fn(
        shell=shell,
        flags_raw=service.env.get('CCB_TMUX_SHELL_FLAGS', ''),
    )
    return service.build_shell_command_fn(shell=shell, flags=flags, cmd_body=cmd_body)


def _tmux_default_shell(service: TmuxRespawnService) -> str:
    try:
        cp = service.tmux_run_fn(['show-option', '-gqv', 'default-shell'], capture=True, timeout=1.0)
    except Exception:
        return ''
    return (getattr(cp, 'stdout', '') or '').strip()


def _set_remain_on_exit(service: TmuxRespawnService, pane_id: str) -> None:
    service.tmux_run_fn(['set-option', '-p', '-t', pane_id, 'remain-on-exit', 'on'], check=False)
