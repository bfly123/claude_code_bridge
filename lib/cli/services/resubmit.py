from __future__ import annotations

from dataclasses import dataclass

from cli.context import CliContext
from cli.models import ParsedResubmitCommand

from .daemon import invoke_mounted_daemon


@dataclass(frozen=True)
class ResubmitSummary:
    project_id: str
    original_message_id: str
    message_id: str
    submission_id: str | None
    jobs: tuple[dict, ...]


def resubmit_message(context: CliContext, command: ParsedResubmitCommand) -> ResubmitSummary:
    payload = invoke_mounted_daemon(
        context,
        allow_restart_stale=True,
        request_fn=lambda client: client.resubmit(command.message_id),
    )
    return ResubmitSummary(
        project_id=context.project.project_id,
        original_message_id=payload['original_message_id'],
        message_id=payload['message_id'],
        submission_id=payload.get('submission_id'),
        jobs=tuple(payload.get('jobs', ())),
    )


__all__ = ['ResubmitSummary', 'resubmit_message']
