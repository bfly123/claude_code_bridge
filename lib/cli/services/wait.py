from __future__ import annotations

from dataclasses import dataclass
import os
import time

from ccbd.socket_client import CcbdClientError
from cli.context import CliContext
from cli.models import ParsedWaitCommand

from .daemon import CcbdServiceError, connect_mounted_daemon

_DEFAULT_TIMEOUT_S = 30.0
_DEFAULT_POLL_INTERVAL_S = 0.1


@dataclass(frozen=True)
class WaitSummary:
    wait_status: str
    project_id: str
    mode: str
    target: str
    resolved_kind: str
    expected_count: int
    received_count: int
    terminal_count: int
    notice_count: int
    waited_s: float
    replies: tuple[dict, ...]


def wait_for_replies(context: CliContext, command: ParsedWaitCommand) -> WaitSummary:
    timeout_s = _resolve_timeout(command.timeout_s)
    poll_interval_s = _resolve_poll_interval()
    started_at = time.monotonic()
    deadline = started_at + timeout_s
    handle = connect_mounted_daemon(context, allow_restart_stale=True)
    assert handle.client is not None

    while True:
        try:
            payload = handle.client.trace(command.target)
        except (CcbdClientError, CcbdServiceError):
            if time.monotonic() >= deadline:
                raise RuntimeError(f'wait {command.mode} timed out for target {command.target}')
            handle = connect_mounted_daemon(context, allow_restart_stale=True)
            assert handle.client is not None
            time.sleep(poll_interval_s)
            continue

        expected_count, replies, terminal_count, notice_count = _latest_replies(payload)
        if expected_count <= 0:
            raise RuntimeError(f'wait target has no attempt routes: {command.target}')
        if command.mode == 'quorum':
            quorum = int(command.quorum or 0)
            if quorum > expected_count:
                raise RuntimeError(
                    f'wait quorum {quorum} exceeds available reply routes {expected_count} for target {command.target}'
                )
        else:
            quorum = 1 if command.mode == 'any' else expected_count

        if len(replies) >= quorum:
            waited_s = time.monotonic() - started_at
            wait_status = 'satisfied' if terminal_count >= quorum else 'notice'
            return WaitSummary(
                wait_status=wait_status,
                project_id=context.project.project_id,
                mode=command.mode,
                target=command.target,
                resolved_kind=str(payload.get('resolved_kind') or ''),
                expected_count=expected_count,
                received_count=len(replies),
                terminal_count=terminal_count,
                notice_count=notice_count,
                waited_s=waited_s,
                replies=tuple(replies),
            )

        if time.monotonic() >= deadline:
            raise RuntimeError(f'wait {command.mode} timed out for target {command.target}')
        time.sleep(poll_interval_s)


def _latest_replies(payload: dict) -> tuple[int, tuple[dict, ...], int, int]:
    latest_attempts: dict[tuple[str, str], dict] = {}
    for attempt in payload.get('attempts') or ():
        key = (str(attempt.get('message_id') or ''), str(attempt.get('agent_name') or ''))
        current = latest_attempts.get(key)
        if current is None or _attempt_sort_key(attempt) > _attempt_sort_key(current):
            latest_attempts[key] = attempt

    replies_by_attempt: dict[str, dict] = {}
    for reply in payload.get('replies') or ():
        attempt_id = str(reply.get('attempt_id') or '')
        if not attempt_id:
            continue
        current = replies_by_attempt.get(attempt_id)
        if current is None or _reply_sort_key(reply) > _reply_sort_key(current):
            replies_by_attempt[attempt_id] = reply

    replies: list[dict] = []
    for attempt in latest_attempts.values():
        reply = replies_by_attempt.get(str(attempt.get('attempt_id') or ''))
        if reply is None:
            continue
        notice = bool(reply.get('notice'))
        replies.append(
            {
                'reply_id': reply.get('reply_id'),
                'message_id': reply.get('message_id'),
                'attempt_id': reply.get('attempt_id'),
                'agent_name': reply.get('agent_name'),
                'job_id': attempt.get('job_id'),
                'terminal_status': reply.get('terminal_status'),
                'notice': notice,
                'notice_kind': reply.get('notice_kind'),
                'last_progress_at': reply.get('last_progress_at'),
                'heartbeat_silence_seconds': reply.get('heartbeat_silence_seconds'),
                'reason': reply.get('reason'),
                'finished_at': reply.get('finished_at'),
                'reply': reply.get('reply') or '',
            }
        )
    replies.sort(key=_reply_sort_key)
    notice_count = sum(1 for reply in replies if bool(reply.get('notice')))
    terminal_count = len(replies) - notice_count
    return len(latest_attempts), tuple(replies), terminal_count, notice_count


def _attempt_sort_key(attempt: dict) -> tuple[int, str, str]:
    return (
        int(attempt.get('retry_index') or 0),
        str(attempt.get('updated_at') or ''),
        str(attempt.get('attempt_id') or ''),
    )


def _reply_sort_key(reply: dict) -> tuple[str, str]:
    return str(reply.get('finished_at') or ''), str(reply.get('reply_id') or '')


def _resolve_timeout(explicit: float | None) -> float:
    if explicit is not None:
        return max(0.1, float(explicit))
    raw = os.environ.get('CCB_WAIT_TIMEOUT_S')
    if raw:
        try:
            return max(0.1, float(raw))
        except Exception:
            pass
    return _DEFAULT_TIMEOUT_S


def _resolve_poll_interval() -> float:
    raw = os.environ.get('CCB_WAIT_POLL_INTERVAL_S')
    if raw:
        try:
            return max(0.01, float(raw))
        except Exception:
            pass
    return _DEFAULT_POLL_INTERVAL_S


__all__ = ['WaitSummary', 'wait_for_replies']
