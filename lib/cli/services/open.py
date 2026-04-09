from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import subprocess
import time

from cli.context import CliContext
from cli.models import ParsedOpenCommand

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
    if shutil.which('tmux') is None:
        raise RuntimeError('tmux is required for `ccb open`')
    handle = _connect_attachable_daemon(context)
    client = handle.client
    if client is None:
        raise RuntimeError('project ccbd is mounted without a client connection')
    payload = client.ping('ccbd')
    tmux_socket_path = str(payload.get('namespace_tmux_socket_path') or '').strip()
    tmux_session_name = str(payload.get('namespace_tmux_session_name') or '').strip()
    workspace_window_name = str(payload.get('namespace_workspace_window_name') or '').strip()
    ui_attachable = bool(payload.get('namespace_ui_attachable'))
    if not tmux_socket_path or not tmux_session_name or not ui_attachable:
        raise RuntimeError('project namespace is not attachable; run `ccb` first')
    env = dict(os.environ)
    env.pop('TMUX', None)
    env.pop('TMUX_PANE', None)
    if not _tmux_has_session(tmux_socket_path, tmux_session_name, env=env):
        raise RuntimeError('project namespace session is missing; run `ccb` first')
    if workspace_window_name and not _tmux_select_window(
        tmux_socket_path,
        f'{tmux_session_name}:{workspace_window_name}',
        env=env,
    ):
        raise RuntimeError('project namespace workspace window is missing; run `ccb` first')
    attach = subprocess.run(
        ['tmux', '-S', tmux_socket_path, 'attach-session', '-t', tmux_session_name],
        check=False,
        env=env,
    )
    if attach.returncode != 0:
        if not _tmux_has_session(tmux_socket_path, tmux_session_name, env=env):
            raise RuntimeError('project namespace session exited before attach completed; run `ccb` first')
        raise RuntimeError('failed to attach project namespace session')
    return OpenSummary(
        project_id=context.project.project_id,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
    )


def _connect_attachable_daemon(context: CliContext):
    deadline = time.time() + _OPEN_RECOVERY_WAIT_S
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
            if not retryable or time.time() >= deadline:
                raise
            time.sleep(_OPEN_RECOVERY_POLL_S)


def _tmux_has_session(tmux_socket_path: str, tmux_session_name: str, *, env: dict[str, str]) -> bool:
    probe = subprocess.run(
        ['tmux', '-S', tmux_socket_path, 'has-session', '-t', tmux_session_name],
        check=False,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return probe.returncode == 0


def _tmux_select_window(tmux_socket_path: str, target: str, *, env: dict[str, str]) -> bool:
    probe = subprocess.run(
        ['tmux', '-S', tmux_socket_path, 'select-window', '-t', target],
        check=False,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return probe.returncode == 0


__all__ = ['OpenSummary', 'open_project']
