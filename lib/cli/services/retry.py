from __future__ import annotations

from dataclasses import dataclass

from ccbd.socket_client import CcbdClientError
from cli.context import CliContext
from cli.models import ParsedRetryCommand

from .daemon import connect_mounted_daemon


@dataclass(frozen=True)
class RetrySummary:
    project_id: str
    target: str
    message_id: str
    original_attempt_id: str
    attempt_id: str
    job_id: str
    agent_name: str
    status: str


def retry_attempt(context: CliContext, command: ParsedRetryCommand) -> RetrySummary:
    handle = connect_mounted_daemon(context, allow_restart_stale=True)
    assert handle.client is not None
    try:
        payload = handle.client.retry(command.target)
    except CcbdClientError:
        handle = connect_mounted_daemon(context, allow_restart_stale=True)
        assert handle.client is not None
        payload = handle.client.retry(command.target)
    return RetrySummary(
        project_id=context.project.project_id,
        target=payload['target'],
        message_id=payload['message_id'],
        original_attempt_id=payload['original_attempt_id'],
        attempt_id=payload['attempt_id'],
        job_id=payload['job_id'],
        agent_name=payload['agent_name'],
        status=payload['status'],
    )


__all__ = ['RetrySummary', 'retry_attempt']
