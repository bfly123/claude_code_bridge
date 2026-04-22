from __future__ import annotations

from cli.context import CliContext
from cli.models import ParsedAckCommand

from .daemon import invoke_mounted_daemon


def ack_reply(context: CliContext, command: ParsedAckCommand) -> dict:
    return invoke_mounted_daemon(
        context,
        allow_restart_stale=True,
        request_fn=lambda client: client.ack(command.agent_name, command.inbound_event_id),
    )


__all__ = ['ack_reply']
