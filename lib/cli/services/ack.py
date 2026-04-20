from __future__ import annotations

from ccbd.socket_client import CcbdClientError
from cli.context import CliContext
from cli.models import ParsedAckCommand

from .daemon import connect_mounted_daemon


def ack_reply(context: CliContext, command: ParsedAckCommand) -> dict:
    handle = connect_mounted_daemon(context, allow_restart_stale=True)
    assert handle.client is not None
    try:
        return handle.client.ack(command.agent_name, command.inbound_event_id)
    except CcbdClientError:
        handle = connect_mounted_daemon(context, allow_restart_stale=True)
        assert handle.client is not None
        return handle.client.ack(command.agent_name, command.inbound_event_id)


__all__ = ['ack_reply']
