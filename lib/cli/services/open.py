from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import subprocess

from cli.context import CliContext
from cli.models import ParsedOpenCommand

from .daemon import connect_mounted_daemon


@dataclass(frozen=True)
class OpenSummary:
    project_id: str
    tmux_socket_path: str
    tmux_session_name: str


def open_project(context: CliContext, command: ParsedOpenCommand) -> OpenSummary:
    del command
    if shutil.which('tmux') is None:
        raise RuntimeError('tmux is required for `ccb open`')
    handle = connect_mounted_daemon(context, allow_restart_stale=False)
    client = handle.client
    if client is None:
        raise RuntimeError('project ccbd is mounted without a client connection')
    payload = client.ping('ccbd')
    tmux_socket_path = str(payload.get('namespace_tmux_socket_path') or '').strip()
    tmux_session_name = str(payload.get('namespace_tmux_session_name') or '').strip()
    ui_attachable = bool(payload.get('namespace_ui_attachable'))
    if not tmux_socket_path or not tmux_session_name or not ui_attachable:
        raise RuntimeError('project namespace is not attachable; run `ccb` first')
    env = dict(os.environ)
    env.pop('TMUX', None)
    env.pop('TMUX_PANE', None)
    if not _tmux_has_session(tmux_socket_path, tmux_session_name, env=env):
        raise RuntimeError('project namespace session is missing; run `ccb` first')
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


def _tmux_has_session(tmux_socket_path: str, tmux_session_name: str, *, env: dict[str, str]) -> bool:
    probe = subprocess.run(
        ['tmux', '-S', tmux_socket_path, 'has-session', '-t', tmux_session_name],
        check=False,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return probe.returncode == 0


__all__ = ['OpenSummary', 'open_project']
