from __future__ import annotations

from cli.context import CliContext
from cli.models import ParsedCancelCommand

from .daemon import connect_mounted_daemon


def cancel_job(context: CliContext, command: ParsedCancelCommand) -> dict:
    handle = connect_mounted_daemon(context, allow_restart_stale=True)
    assert handle.client is not None
    return handle.client.cancel(command.job_id)
