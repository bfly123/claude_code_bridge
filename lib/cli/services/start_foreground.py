from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import subprocess
import time

from cli.context import CliContext
from ccbd.socket_client import CcbdClient, CcbdClientError
from .daemon_runtime.policy import CONTROL_PLANE_RPC_TIMEOUT_S

_ATTACH_ESTABLISH_TIMEOUT_S = 1.5
_ATTACH_ESTABLISH_POLL_INTERVAL_S = 0.05
_ATTACH_TARGET_READY_TIMEOUT_S = 2.0
_ATTACH_TARGET_READY_POLL_INTERVAL_S = 0.05


@dataclass(frozen=True)
class ForegroundAttachSummary:
    project_id: str
    tmux_socket_path: str
    tmux_session_name: str


class ForegroundAttachError(RuntimeError):
    pass


def attach_started_project_namespace(context: CliContext) -> ForegroundAttachSummary:
    if shutil.which('tmux') is None:
        raise ForegroundAttachError('tmux is required for interactive `ccb`')
    client = _client_for_started_project(context)
    env = _attach_env()
    payload = _wait_for_attach_target(client, env=env)
    tmux_socket_path = str(payload.get('namespace_tmux_socket_path') or '').strip()
    tmux_session_name = str(payload.get('namespace_tmux_session_name') or '').strip()
    summary = ForegroundAttachSummary(
        project_id=context.project.project_id,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
    )
    attach = subprocess.Popen(
        ['tmux', '-S', tmux_socket_path, 'attach-session', '-t', tmux_session_name],
        env=env,
    )
    attached = _wait_for_attach_established(
        attach,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        env=env,
    )
    returncode = attach.wait()
    if attached:
        return summary
    if returncode != 0 and not _tmux_has_session(tmux_socket_path, tmux_session_name, env=env):
        raise ForegroundAttachError('project namespace session exited before foreground attach completed')
    raise ForegroundAttachError('failed to attach project namespace after successful `ccb` start')


def _wait_for_attach_established(
    attach: subprocess.Popen[bytes] | subprocess.Popen[str],
    *,
    tmux_socket_path: str,
    tmux_session_name: str,
    env: dict[str, str],
) -> bool:
    deadline = time.monotonic() + _ATTACH_ESTABLISH_TIMEOUT_S
    while True:
        if _tmux_client_pid_attached(
            tmux_socket_path,
            tmux_session_name,
            client_pid=attach.pid,
            env=env,
        ):
            return True
        if attach.poll() is not None:
            return False
        if time.monotonic() >= deadline:
            return True
        time.sleep(_ATTACH_ESTABLISH_POLL_INTERVAL_S)


def _tmux_client_pid_attached(
    tmux_socket_path: str,
    tmux_session_name: str,
    *,
    client_pid: int,
    env: dict[str, str],
) -> bool:
    return client_pid in _tmux_list_client_pids(
        tmux_socket_path,
        tmux_session_name,
        env=env,
    )


def _wait_for_attach_target(client, *, env: dict[str, str]) -> dict[str, object]:
    deadline = time.monotonic() + _ATTACH_TARGET_READY_TIMEOUT_S
    last_error = 'project namespace is not attachable after successful `ccb` start'
    while True:
        try:
            payload = client.ping('ccbd')
        except CcbdClientError as exc:
            last_error = f'project ccbd is unavailable after successful `ccb` start: {exc}'
        else:
            ready, error = _attach_target_ready(payload, env=env)
            if ready:
                return payload
            last_error = error
        if time.monotonic() >= deadline:
            raise ForegroundAttachError(last_error)
        time.sleep(_ATTACH_TARGET_READY_POLL_INTERVAL_S)


def _attach_target_ready(payload: dict[str, object], *, env: dict[str, str]) -> tuple[bool, str]:
    tmux_socket_path = str(payload.get('namespace_tmux_socket_path') or '').strip()
    tmux_session_name = str(payload.get('namespace_tmux_session_name') or '').strip()
    workspace_window_name = str(payload.get('namespace_workspace_window_name') or '').strip()
    ui_attachable = bool(payload.get('namespace_ui_attachable'))
    if not tmux_socket_path or not tmux_session_name or not ui_attachable:
        return False, 'project namespace is not attachable after successful `ccb` start'
    if not _tmux_has_session(tmux_socket_path, tmux_session_name, env=env):
        return False, 'project namespace session is missing after successful `ccb` start'
    if workspace_window_name and not _tmux_select_window(
        tmux_socket_path,
        f'{tmux_session_name}:{workspace_window_name}',
        env=env,
    ):
        return False, 'project namespace workspace window is missing after successful `ccb` start'
    return True, ''


def _tmux_list_client_pids(
    tmux_socket_path: str,
    tmux_session_name: str,
    *,
    env: dict[str, str],
) -> tuple[int, ...]:
    probe = subprocess.run(
        ['tmux', '-S', tmux_socket_path, 'list-clients', '-t', tmux_session_name, '-F', '#{client_pid}'],
        check=False,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if probe.returncode != 0:
        return ()
    client_pids: list[int] = []
    for line in (probe.stdout or '').splitlines():
        value = line.strip()
        if not value:
            continue
        try:
            client_pids.append(int(value))
        except ValueError:
            continue
    return tuple(client_pids)


def _client_for_started_project(context: CliContext):
    try:
        return _build_control_plane_client(context.paths.ccbd_socket_path)
    except CcbdClientError as exc:
        raise ForegroundAttachError(f'project ccbd is unavailable after successful `ccb` start: {exc}') from exc


def _build_control_plane_client(socket_path):
    try:
        return CcbdClient(socket_path, timeout_s=CONTROL_PLANE_RPC_TIMEOUT_S)
    except TypeError:
        # Some test doubles or compatibility shims expose only the legacy single-arg constructor.
        return CcbdClient(socket_path)


def _attach_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop('TMUX', None)
    env.pop('TMUX_PANE', None)
    return env


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


__all__ = [
    'ForegroundAttachError',
    'ForegroundAttachSummary',
    'attach_started_project_namespace',
]
