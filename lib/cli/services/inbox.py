from __future__ import annotations

from ccbd.socket_client import CcbdClientError
from cli.context import CliContext
from cli.models import ParsedInboxCommand

from .daemon import connect_mounted_daemon


def inbox_target(context: CliContext, command: ParsedInboxCommand) -> dict:
    handle = connect_mounted_daemon(context, allow_restart_stale=True)
    assert handle.client is not None
    try:
        return handle.client.inbox(command.agent_name)
    except CcbdClientError:
        handle = connect_mounted_daemon(context, allow_restart_stale=True)
        assert handle.client is not None
        return handle.client.inbox(command.agent_name)


__all__ = ['inbox_target']
