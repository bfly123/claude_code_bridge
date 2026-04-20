from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import subprocess

from cli.context import CliContext
from ccbd.socket_client import CcbdClient, CcbdClientError


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
    payload = client.ping('ccbd')
    tmux_socket_path = str(payload.get('namespace_tmux_socket_path') or '').strip()
    tmux_session_name = str(payload.get('namespace_tmux_session_name') or '').strip()
    workspace_window_name = str(payload.get('namespace_workspace_window_name') or '').strip()
    ui_attachable = bool(payload.get('namespace_ui_attachable'))
    if not tmux_socket_path or not tmux_session_name or not ui_attachable:
        raise ForegroundAttachError('project namespace is not attachable after successful `ccb` start')
    env = _attach_env()
    if not _tmux_has_session(tmux_socket_path, tmux_session_name, env=env):
        raise ForegroundAttachError('project namespace session is missing after successful `ccb` start')
    if workspace_window_name and not _tmux_select_window(
        tmux_socket_path,
        f'{tmux_session_name}:{workspace_window_name}',
        env=env,
    ):
        raise ForegroundAttachError('project namespace workspace window is missing after successful `ccb` start')
    attach = subprocess.run(
        ['tmux', '-S', tmux_socket_path, 'attach-session', '-t', tmux_session_name],
        check=False,
        env=env,
    )
    if attach.returncode != 0:
        if not _tmux_has_session(tmux_socket_path, tmux_session_name, env=env):
            raise ForegroundAttachError('project namespace session exited before foreground attach completed')
        raise ForegroundAttachError('failed to attach project namespace after successful `ccb` start')
    return ForegroundAttachSummary(
        project_id=context.project.project_id,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
    )


def _client_for_started_project(context: CliContext):
    try:
        return CcbdClient(context.paths.ccbd_socket_path)
    except CcbdClientError as exc:
        raise ForegroundAttachError(f'project ccbd is unavailable after successful `ccb` start: {exc}') from exc


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
