from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from typing import Callable

_TMUX_RESPAWN_RETRY_TIMEOUT_S = 1.0
_TMUX_RESPAWN_RETRY_INTERVAL_S = 0.05
_TMUX_RESPAWN_TRANSIENT_ERROR_MARKERS = (
    'fork failed',
    'no server running',
    'server exited unexpectedly',
)


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
        _run_respawn_command(self, tmux_args)
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


def _run_respawn_command(service: TmuxRespawnService, tmux_args: list[str]) -> None:
    deadline = time.monotonic() + _TMUX_RESPAWN_RETRY_TIMEOUT_S
    last_error: RuntimeError | None = None
    while True:
        try:
            _run_respawn_once(service, tmux_args)
            return
        except RuntimeError as exc:
            if not _is_retryable_respawn_error(exc):
                raise
            last_error = exc
        if time.monotonic() >= deadline:
            if last_error is not None:
                raise last_error
            raise RuntimeError('respawn pane failed')
        time.sleep(_TMUX_RESPAWN_RETRY_INTERVAL_S)


def _run_respawn_once(service: TmuxRespawnService, tmux_args: list[str]) -> None:
    cp = service.tmux_run_fn(tmux_args, check=False, capture=True)
    if int(getattr(cp, 'returncode', 1) or 0) == 0:
        return
    raise RuntimeError(_respawn_failure_text(cp, tmux_args))


def _respawn_failure_text(cp: subprocess.CompletedProcess | object, tmux_args: list[str]) -> str:
    stderr = str(getattr(cp, 'stderr', '') or '').strip()
    stdout = str(getattr(cp, 'stdout', '') or '').strip()
    detail = stderr or stdout or f'tmux command failed: {" ".join(tmux_args)}'
    return f'respawn pane failed: {detail}'


def _is_retryable_respawn_error(exc: RuntimeError) -> bool:
    text = str(exc).strip().lower()
    return any(marker in text for marker in _TMUX_RESPAWN_TRANSIENT_ERROR_MARKERS)
