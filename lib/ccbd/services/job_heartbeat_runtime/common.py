from __future__ import annotations

from ccbd.api_models import JobRecord


def heartbeat_notice_body(job: JobRecord, *, decision, snapshot) -> str:
    lines = [
        'CCB_HEARTBEAT '
        f'from={job.agent_name} '
        f'job={job.job_id} '
        f'notice={decision.notice_count} '
        f'silent_for={format_silence(decision.silence_seconds)} '
        f'last_progress={decision.last_progress_at}',
    ]
    task_id = str(job.request.task_id or '').strip()
    if task_id:
        lines[0] = f'{lines[0]} task={task_id}'
    preview = snapshot_preview(snapshot)
    if preview:
        lines.extend(['', preview])
    return '\n'.join(lines).rstrip()


def heartbeat_diagnostics(
    job: JobRecord,
    *,
    decision,
    snapshot,
    mailbox_target: str | None,
    subject_kind: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        'notice': True,
        'notice_kind': 'heartbeat',
        'heartbeat_subject_kind': subject_kind,
        'heartbeat_action': decision.action.value,
        'heartbeat_notice_count': decision.notice_count,
        'heartbeat_silence_seconds': round(float(decision.silence_seconds), 3),
        'last_progress_at': decision.last_progress_at,
        'job_id': job.job_id,
        'task_id': str(job.request.task_id or '').strip() or None,
        'caller_actor': job.request.from_actor,
        'caller_mailbox': mailbox_target,
    }
    preview = snapshot_preview(snapshot)
    if preview:
        payload['reply_preview'] = preview
    return payload


def snapshot_preview(snapshot) -> str:
    if snapshot is None:
        return ''
    return str(snapshot.latest_reply_preview or '').strip()


def snapshot_is_terminal(snapshot) -> bool:
    if snapshot is None:
        return False
    try:
        if bool(getattr(snapshot.state, 'terminal', False)):
            return True
    except Exception:
        return False
    try:
        return bool(getattr(snapshot.latest_decision, 'terminal', False))
    except Exception:
        return False


def format_silence(value: float) -> str:
    try:
        seconds = int(round(float(value)))
    except Exception:
        return str(value)
    return f'{seconds}s'


__all__ = [
    'format_silence',
    'heartbeat_diagnostics',
    'heartbeat_notice_body',
    'snapshot_is_terminal',
    'snapshot_preview',
]
