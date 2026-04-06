from __future__ import annotations


def format_reply_delivery_body(dispatcher, reply) -> str:
    attempt = dispatcher._message_bureau_control._attempt_store.get_latest(reply.attempt_id)
    source_job = None
    if attempt is not None:
        source_job = dispatcher.get_job(attempt.job_id) if hasattr(dispatcher, 'get_job') else None
        if source_job is None:
            from ..records import get_job

            source_job = get_job(dispatcher, attempt.job_id)
    if str(reply.diagnostics.get('notice_kind') or '').strip().lower() == 'heartbeat':
        return format_heartbeat_delivery_body(reply, source_job=source_job)
    header = [
        'CCB_REPLY',
        f'from={reply.agent_name}',
        f'reply={reply.reply_id}',
        f'status={reply.terminal_status.value}',
    ]
    if source_job is not None:
        header.append(f'job={source_job.job_id}')
        task_id = str(source_job.request.task_id or '').strip()
        if task_id:
            header.append(f'task={task_id}')
    body = reply.reply or '(empty reply)'
    return '\n'.join((' '.join(header), '', body)).rstrip()


def format_heartbeat_delivery_body(reply, *, source_job) -> str:
    diagnostics = dict(reply.diagnostics or {})
    lines = [
        'CCB_NOTICE '
        f'kind=heartbeat '
        f'from={reply.agent_name} '
        f'reply={reply.reply_id}'
    ]
    job_id = str(diagnostics.get('job_id') or '').strip()
    if job_id:
        lines[0] = f'{lines[0]} job={job_id}'
    elif source_job is not None:
        lines[0] = f'{lines[0]} job={source_job.job_id}'
    if source_job is not None and source_job.request.task_id:
        lines[0] = f'{lines[0]} task={source_job.request.task_id}'
    last_progress_at = str(diagnostics.get('last_progress_at') or '').strip()
    if last_progress_at:
        lines[0] = f'{lines[0]} last_progress={last_progress_at}'
    silence_seconds = diagnostics.get('heartbeat_silence_seconds')
    if silence_seconds is not None:
        lines[0] = f'{lines[0]} silent_for={format_silence_seconds(silence_seconds)}'
    body = str(reply.reply or '').strip()
    if body:
        lines.extend(['', body])
    else:
        lines.extend(['', '(empty notice)'])
    return '\n'.join(lines).rstrip()


def format_silence_seconds(value) -> str:
    try:
        seconds = int(round(float(value)))
    except Exception:
        return str(value)
    return f'{seconds}s'


__all__ = ['format_reply_delivery_body']
