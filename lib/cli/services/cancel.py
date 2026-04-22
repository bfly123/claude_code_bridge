from __future__ import annotations

from cli.context import CliContext
from cli.models import ParsedCancelCommand

from .daemon import invoke_mounted_daemon


def cancel_job(context: CliContext, command: ParsedCancelCommand) -> dict:
    return invoke_mounted_daemon(
        context,
        allow_restart_stale=True,
        request_fn=lambda client: client.cancel(command.job_id),
    )
