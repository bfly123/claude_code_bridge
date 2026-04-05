from __future__ import annotations

from ccbd.socket_client import CcbdClientError
from cli.context import CliContext
from cli.models import ParsedTraceCommand

from .daemon import connect_mounted_daemon


def trace_target(context: CliContext, command: ParsedTraceCommand) -> dict:
    handle = connect_mounted_daemon(context, allow_restart_stale=True)
    assert handle.client is not None
    try:
        return handle.client.trace(command.target)
    except CcbdClientError:
        handle = connect_mounted_daemon(context, allow_restart_stale=True)
        assert handle.client is not None
        return handle.client.trace(command.target)


__all__ = ['trace_target']
