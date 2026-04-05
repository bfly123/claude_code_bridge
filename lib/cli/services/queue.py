from __future__ import annotations

from ccbd.socket_client import CcbdClientError
from cli.context import CliContext
from cli.models import ParsedQueueCommand

from .daemon import connect_mounted_daemon


def queue_target(context: CliContext, command: ParsedQueueCommand) -> dict:
    handle = connect_mounted_daemon(context, allow_restart_stale=True)
    assert handle.client is not None
    try:
        return handle.client.queue(command.target)
    except CcbdClientError:
        handle = connect_mounted_daemon(context, allow_restart_stale=True)
        assert handle.client is not None
        return handle.client.queue(command.target)


__all__ = ['queue_target']
