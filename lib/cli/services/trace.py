from __future__ import annotations

from cli.context import CliContext
from cli.models import ParsedTraceCommand

from .daemon import invoke_mounted_daemon


def trace_target(context: CliContext, command: ParsedTraceCommand) -> dict:
    return invoke_mounted_daemon(
        context,
        allow_restart_stale=True,
        request_fn=lambda client: client.trace(command.target),
    )


__all__ = ['trace_target']
