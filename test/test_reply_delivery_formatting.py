from __future__ import annotations

from types import SimpleNamespace

from ccbd.services.dispatcher_runtime.reply_delivery_runtime.formatting import (
    format_reply_delivery_body,
    format_silence_seconds,
)


def test_format_reply_delivery_body_includes_job_and_task() -> None:
    reply = SimpleNamespace(
        attempt_id='att-1',
        agent_name='agent2',
        reply_id='rep-1',
        terminal_status=SimpleNamespace(value='succeeded'),
        diagnostics={},
        reply='done',
    )
    source_job = SimpleNamespace(job_id='job-1', request=SimpleNamespace(task_id='task-9'))
    dispatcher = SimpleNamespace(
        _message_bureau_control=SimpleNamespace(
            _attempt_store=SimpleNamespace(get_latest=lambda attempt_id: SimpleNamespace(job_id='job-1'))
        ),
        get_job=lambda job_id: source_job,
    )

    body = format_reply_delivery_body(dispatcher, reply)

    assert body == 'CCB_REPLY from=agent2 reply=rep-1 status=succeeded job=job-1 task=task-9\n\ndone'


def test_format_reply_delivery_body_formats_heartbeat_notice() -> None:
    reply = SimpleNamespace(
        attempt_id='att-1',
        agent_name='agent3',
        reply_id='rep-2',
        terminal_status=SimpleNamespace(value='running'),
        diagnostics={
            'notice_kind': 'heartbeat',
            'heartbeat_silence_seconds': 601,
            'last_progress_at': '2026-04-07T04:00:00Z',
        },
        reply='still running',
    )
    source_job = SimpleNamespace(job_id='job-2', request=SimpleNamespace(task_id='task-3'))
    dispatcher = SimpleNamespace(
        _message_bureau_control=SimpleNamespace(
            _attempt_store=SimpleNamespace(get_latest=lambda attempt_id: SimpleNamespace(job_id='job-2'))
        ),
        get_job=lambda job_id: source_job,
    )

    body = format_reply_delivery_body(dispatcher, reply)

    assert body == (
        'CCB_NOTICE kind=heartbeat from=agent3 reply=rep-2 job=job-2 '
        'task=task-3 last_progress=2026-04-07T04:00:00Z silent_for=601s\n\nstill running'
    )
    assert format_silence_seconds('10.2') == '10s'
