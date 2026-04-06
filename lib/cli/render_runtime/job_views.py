from __future__ import annotations

from collections.abc import Mapping

from .common import display_text, render_mapping


def render_ask(summary) -> tuple[str, ...]:
    jobs = tuple(summary.jobs or ())
    if len(jobs) == 1:
        job = jobs[0]
        target = job.get('target_name') or job.get('agent_name')
        return (f'accepted job={job["job_id"]} target={target}',)
    rendered_jobs = ','.join(
        f'{job["job_id"]}@{job.get("target_name") or job.get("agent_name")}'
        for job in jobs
    )
    return (f'accepted jobs={rendered_jobs}',)


def render_resubmit(summary) -> tuple[str, ...]:
    lines = [
        'resubmit_status: accepted',
        f'project_id: {summary.project_id}',
        f'original_message_id: {summary.original_message_id}',
        f'message_id: {summary.message_id}',
        f'submission_id: {summary.submission_id}',
    ]
    for job in summary.jobs:
        target = job.get('target_name') or job.get('agent_name')
        lines.append(f'job: {job["job_id"]} {target} {job["status"]}')
    return tuple(lines)


def render_retry(summary) -> tuple[str, ...]:
    return (
        'retry_status: accepted',
        f'project_id: {summary.project_id}',
        f'target: {summary.target}',
        f'message_id: {summary.message_id}',
        f'original_attempt_id: {summary.original_attempt_id}',
        f'attempt_id: {summary.attempt_id}',
        f'job_id: {summary.job_id}',
        f'agent_name: {summary.agent_name}',
        f'status: {summary.status}',
    )


def render_wait(summary) -> tuple[str, ...]:
    lines = [
        f'wait_status: {getattr(summary, "wait_status", "satisfied")}',
        f'project_id: {summary.project_id}',
        f'mode: {summary.mode}',
        f'target: {summary.target}',
        f'resolved_kind: {summary.resolved_kind}',
        f'expected_count: {summary.expected_count}',
        f'received_count: {summary.received_count}',
        f'terminal_count: {getattr(summary, "terminal_count", summary.received_count)}',
        f'notice_count: {getattr(summary, "notice_count", 0)}',
        f'waited_s: {summary.waited_s:.3f}',
    ]
    for reply in summary.replies:
        lines.append(
            'reply: '
            f'id={reply["reply_id"]} message={reply["message_id"]} attempt={reply["attempt_id"]} '
            f'agent={reply["agent_name"]} job={reply.get("job_id")} terminal={reply["terminal_status"]} '
            f'notice={str(bool(reply.get("notice"))).lower()} kind={reply.get("notice_kind")} '
            f'finished={reply["finished_at"]} reason={reply.get("reason")}'
        )
        if reply.get('last_progress_at') is not None:
            lines.append(f'reply_last_progress_at: {reply.get("last_progress_at")}')
        if reply.get('heartbeat_silence_seconds') is not None:
            lines.append(f'reply_heartbeat_silence_seconds: {reply.get("heartbeat_silence_seconds")}')
        lines.append(f'reply_text: {display_text(reply.get("reply"))}')
    return tuple(lines)


def render_watch_batch(batch) -> tuple[str, ...]:
    lines: list[str] = []
    for event in batch.events:
        target = event.get('target_name') or event.get('agent_name')
        lines.append(
            f'event: {event["event_id"]} {event["job_id"]} {target} {event["type"]} {event["timestamp"]}'
        )
    if batch.terminal:
        target = getattr(batch, 'target_name', '') or getattr(batch, 'agent_name', '')
        lines.extend(
            [
                'watch_status: terminal',
                f'job_id: {batch.job_id}',
                f'agent_name: {batch.agent_name}',
                f'target_name: {target}',
                f'status: {batch.status}',
                f'reply: {display_text(batch.reply)}',
            ]
        )
    return tuple(lines)


def render_cancel(payload: Mapping[str, object]) -> tuple[str, ...]:
    return ('cancel_status: ok', *render_mapping(payload))


__all__ = [
    'render_ask',
    'render_cancel',
    'render_resubmit',
    'render_retry',
    'render_wait',
    'render_watch_batch',
]
