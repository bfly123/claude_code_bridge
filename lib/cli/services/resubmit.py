from __future__ import annotations

from dataclasses import dataclass

from ccbd.socket_client import CcbdClientError
from cli.context import CliContext
from cli.models import ParsedResubmitCommand

from .daemon import connect_mounted_daemon


@dataclass(frozen=True)
class ResubmitSummary:
    project_id: str
    original_message_id: str
    message_id: str
    submission_id: str | None
    jobs: tuple[dict, ...]


def resubmit_message(context: CliContext, command: ParsedResubmitCommand) -> ResubmitSummary:
    handle = connect_mounted_daemon(context, allow_restart_stale=True)
    assert handle.client is not None
    try:
        payload = handle.client.resubmit(command.message_id)
    except CcbdClientError:
        handle = connect_mounted_daemon(context, allow_restart_stale=True)
        assert handle.client is not None
        payload = handle.client.resubmit(command.message_id)
    return ResubmitSummary(
        project_id=context.project.project_id,
        original_message_id=payload['original_message_id'],
        message_id=payload['message_id'],
        submission_id=payload.get('submission_id'),
        jobs=tuple(payload.get('jobs', ())),
    )


__all__ = ['ResubmitSummary', 'resubmit_message']
