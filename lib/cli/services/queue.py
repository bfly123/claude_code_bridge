from __future__ import annotations

from cli.context import CliContext
from cli.models import ParsedQueueCommand

from .daemon import invoke_mounted_daemon


def queue_target(context: CliContext, command: ParsedQueueCommand) -> dict:
    return invoke_mounted_daemon(
        context,
        allow_restart_stale=True,
        request_fn=lambda client: client.queue(command.target),
    )


__all__ = ['queue_target']
