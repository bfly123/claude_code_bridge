from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import subprocess
import time

from cli.context import CliContext
from cli.models import ParsedOpenCommand
from terminal_runtime import build_mux_backend

from .daemon import connect_mounted_daemon
from .daemon_runtime import CcbdServiceError


_CONFIG_DRIFT_ERROR = 'mounted ccbd config does not match current .ccb/ccb.config'
_UNMOUNTED_ERRORS = frozenset(
    {
        'project ccbd is unmounted; run `ccb [agents...]` first',
        'project ccbd is not mounted; run `ccb [agents...]` first',
    }
)
_OPEN_RECOVERY_WAIT_S = 2.0
_OPEN_RECOVERY_POLL_S = 0.05


@dataclass(frozen=True)
class OpenSummary:
    project_id: str
    tmux_socket_path: str
    tmux_session_name: str


def open_project(context: CliContext, command: ParsedOpenCommand) -> OpenSummary:
    del command
    handle = _connect_attachable_daemon(context)
    client = handle.client
    if client is None:
        raise RuntimeError('project ccbd is mounted without a client connection')
    payload = client.ping('ccbd')
    backend_ref = str(payload.get('namespace_backend_ref') or payload.get('namespace_tmux_socket_path') or '').strip()
    session_name = str(payload.get('namespace_session_name') or payload.get('namespace_tmux_session_name') or '').strip()
    workspace_name = str(payload.get('namespace_workspace_name') or payload.get('namespace_workspace_window_name') or '').strip()
    ui_attachable = bool(payload.get('namespace_ui_attachable'))
    backend_impl = str(payload.get('namespace_backend_impl') or payload.get('backend_impl') or '').strip() or None
    if not session_name or not ui_attachable:
        raise RuntimeError('project namespace is not attachable; run `ccb` first')
    backend = build_mux_backend(backend_impl=backend_impl, socket_path=backend_ref or None)
    env = dict(os.environ)
    env.pop('TMUX', None)
    env.pop('TMUX_PANE', None)
    if str(backend_impl or 'tmux').strip().lower() == 'tmux':
        return _open_tmux_namespace(
            context,
            tmux_socket_path=backend_ref,
            tmux_session_name=session_name,
            workspace_window_name=workspace_name,
            env=env,
        )
    if not backend.session_exists(session_name):
        raise RuntimeError('project namespace session is missing; run `ccb` first')
    if workspace_name and not backend.select_window(f'{session_name}:{workspace_name}'):
        raise RuntimeError('project namespace workspace window is missing; run `ccb` first')
    attach_rc = backend.attach_session(session_name, env=env)
    if attach_rc != 0:
        if not backend.session_exists(session_name):
            raise RuntimeError('project namespace session exited before attach completed; run `ccb` first')
        raise RuntimeError('failed to attach project namespace session')
    return OpenSummary(
        project_id=context.project.project_id,
        tmux_socket_path=backend_ref,
        tmux_session_name=session_name,
    )


def _open_tmux_namespace(
    context: CliContext,
    *,
    tmux_socket_path: str,
    tmux_session_name: str,
    workspace_window_name: str,
    env: dict[str, str],
) -> OpenSummary:
    if not shutil.which('tmux'):
        raise RuntimeError('tmux is not installed or not found in PATH')
    base = ['tmux']
    if tmux_socket_path:
        base.extend(['-S', tmux_socket_path])
    if _run_tmux(base + ['has-session', '-t', tmux_session_name], env=env) != 0:
        raise RuntimeError('project namespace session is missing; run `ccb` first')
    if workspace_window_name:
        target = f'{tmux_session_name}:{workspace_window_name}'
        if _run_tmux(base + ['select-window', '-t', target], env=env) != 0:
            raise RuntimeError('project namespace workspace window is missing; run `ccb` first')
    if _run_tmux(base + ['attach-session', '-t', tmux_session_name], env=env) != 0:
        if _run_tmux(base + ['has-session', '-t', tmux_session_name], env=env) != 0:
            raise RuntimeError('project namespace session exited before attach completed; run `ccb` first')
        raise RuntimeError('failed to attach project namespace session')
    return OpenSummary(
        project_id=context.project.project_id,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
    )


def _run_tmux(args: list[str], *, env: dict[str, str]) -> int:
    return subprocess.run(args, env=env).returncode


def _connect_attachable_daemon(context: CliContext):
    tolerate_interrupts = _should_tolerate_keyboard_interrupt(context)
    deadline = _deadline_after(_OPEN_RECOVERY_WAIT_S, tolerate_interrupts=tolerate_interrupts)
    observed_config_drift = False
    while True:
        try:
            return connect_mounted_daemon(context, allow_restart_stale=False)
        except CcbdServiceError as exc:
            message = str(exc)
            retryable = False
            if message == _CONFIG_DRIFT_ERROR:
                observed_config_drift = True
                retryable = True
            elif observed_config_drift and message in _UNMOUNTED_ERRORS:
                retryable = True
            if not retryable or _deadline_expired(deadline, tolerate_interrupts=tolerate_interrupts):
                raise
            _sleep(_OPEN_RECOVERY_POLL_S, tolerate_interrupts=tolerate_interrupts)


def _should_tolerate_keyboard_interrupt(context: CliContext) -> bool:
    return getattr(context.paths, 'ccbd_ipc_kind', None) == 'named_pipe'


def _deadline_after(duration_s: float, *, tolerate_interrupts: bool) -> float:
    return _monotonic_now(tolerate_interrupts=tolerate_interrupts) + max(0.0, float(duration_s))


def _deadline_expired(deadline: float, *, tolerate_interrupts: bool) -> bool:
    return _monotonic_now(tolerate_interrupts=tolerate_interrupts) >= deadline


def _monotonic_now(*, tolerate_interrupts: bool) -> float:
    while True:
        try:
            return time.monotonic()
        except KeyboardInterrupt:
            if not tolerate_interrupts:
                raise


def _sleep(duration_s: float, *, tolerate_interrupts: bool) -> None:
    deadline = _deadline_after(duration_s, tolerate_interrupts=tolerate_interrupts)
    while True:
        remaining = deadline - _monotonic_now(tolerate_interrupts=tolerate_interrupts)
        if remaining <= 0:
            return
        try:
            time.sleep(remaining)
            return
        except KeyboardInterrupt:
            if not tolerate_interrupts:
                raise


__all__ = ['OpenSummary', 'open_project']
