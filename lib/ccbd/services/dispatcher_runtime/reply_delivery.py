from __future__ import annotations

from ccbd.api_models import DeliveryScope, JobRecord, JobStatus, MessageEnvelope, TargetKind
from mailbox_kernel import InboundEventRecord, InboundEventStatus, InboundEventType
from message_bureau.models import AttemptRecord, AttemptState, MessageRecord, MessageState
from message_bureau.reply_payloads import compose_reply_payload, delivery_job_id_from_payload, reply_id_from_payload

from .records import append_event, get_job
from .submission_models import _JobDraft
from .submission_recording import _build_job_record, _enqueue_submitted_job

_REPLY_DELIVERY_MESSAGE_TYPE = 'reply_delivery'
_REPLY_DELIVERY_PROVIDER_OPTION = 'reply_delivery'
_REPLY_DELIVERY_INBOUND_EVENT_OPTION = 'reply_delivery_inbound_event_id'
_REPLY_DELIVERY_REPLY_ID_OPTION = 'reply_delivery_reply_id'
_PENDING_JOB_STATUSES = frozenset({JobStatus.ACCEPTED, JobStatus.QUEUED})
_TERMINAL_JOB_STATUSES = frozenset(
    {
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.INCOMPLETE,
        JobStatus.CANCELLED,
    }
)


def prepare_reply_deliveries(dispatcher) -> tuple[JobRecord, ...]:
    control = getattr(dispatcher, '_message_bureau_control', None)
    bureau = getattr(dispatcher, '_message_bureau', None)
    if control is None or bureau is None:
        return ()

    created: list[JobRecord] = []
    for agent_name in dispatcher._config.agents:
        job = _prepare_agent_reply_delivery(dispatcher, agent_name)
        if job is not None:
            created.append(job)
    return tuple(created)


def claimable_reply_delivery_job_ids(dispatcher, agent_name: str) -> tuple[str, ...]:
    head = _head_reply_event(dispatcher, agent_name)
    if head is None:
        return ()
    job_id = delivery_job_id_from_payload(head.payload_ref)
    if not job_id:
        return ()
    current = get_job(dispatcher, job_id)
    if current is None:
        return ()
    if current.status not in _PENDING_JOB_STATUSES:
        return ()
    return (job_id,)


def claim_reply_delivery_start(dispatcher, job: JobRecord, *, started_at: str) -> bool:
    if not is_reply_delivery_job(job):
        return True
    inbound_event_id = _reply_delivery_inbound_event_id(job)
    if not inbound_event_id:
        return False
    head = _head_reply_event(dispatcher, job.agent_name)
    if head is None or head.inbound_event_id != inbound_event_id:
        return False
    claimed = dispatcher._message_bureau_control._mailbox_kernel.claim(
        job.agent_name,
        inbound_event_id,
        started_at=started_at,
    )
    return claimed is not None


def resolve_reply_delivery_terminal(dispatcher, job: JobRecord, *, finished_at: str) -> None:
    if not is_reply_delivery_job(job):
        return

    inbound_event_id = _reply_delivery_inbound_event_id(job)
    reply_id = _reply_delivery_reply_id(job)
    if not inbound_event_id or not reply_id:
        return

    control = dispatcher._message_bureau_control
    current = control._inbound_store.get_latest(job.agent_name, inbound_event_id)
    if current is None:
        return

    if job.status is JobStatus.COMPLETED:
        control._mailbox_kernel.consume(job.agent_name, inbound_event_id, finished_at=finished_at)
        append_event(
            dispatcher,
            job,
            'reply_delivery_consumed',
            {
                'inbound_event_id': inbound_event_id,
                'reply_id': reply_id,
            },
            timestamp=finished_at,
        )
        return

    _rewrite_reply_head(
        dispatcher,
        current,
        reply_id=reply_id,
        delivery_job_id=None,
        status=InboundEventStatus.QUEUED,
        updated_at=finished_at,
        clear_progress=True,
    )
    append_event(
        dispatcher,
        job,
        'reply_delivery_requeued',
        {
            'inbound_event_id': inbound_event_id,
            'reply_id': reply_id,
            'terminal_status': job.status.value,
        },
        timestamp=finished_at,
    )


def is_reply_delivery_job(job: JobRecord) -> bool:
    if str(job.request.message_type or '').strip().lower() == _REPLY_DELIVERY_MESSAGE_TYPE:
        return True
    return bool(job.provider_options.get(_REPLY_DELIVERY_PROVIDER_OPTION))


def _prepare_agent_reply_delivery(dispatcher, agent_name: str) -> JobRecord | None:
    head = _head_reply_event(dispatcher, agent_name)
    if head is None:
        return None
    reply_id = reply_id_from_payload(head.payload_ref)
    if not reply_id:
        return None

    delivery_job_id = delivery_job_id_from_payload(head.payload_ref)
    if delivery_job_id:
        current = get_job(dispatcher, delivery_job_id)
        if current is None:
            _rewrite_reply_head(
                dispatcher,
                head,
                reply_id=reply_id,
                delivery_job_id=None,
                status=InboundEventStatus.QUEUED,
                updated_at=dispatcher._clock(),
                clear_progress=True,
            )
            head = _head_reply_event(dispatcher, agent_name)
            if head is None:
                return None
        elif current.status in _PENDING_JOB_STATUSES or current.status is JobStatus.RUNNING:
            return None
        elif current.status is JobStatus.COMPLETED:
            resolve_reply_delivery_terminal(dispatcher, current, finished_at=current.updated_at)
            return None
        elif current.status in _TERMINAL_JOB_STATUSES:
            _rewrite_reply_head(
                dispatcher,
                head,
                reply_id=reply_id,
                delivery_job_id=None,
                status=InboundEventStatus.QUEUED,
                updated_at=dispatcher._clock(),
                clear_progress=True,
            )
            head = _head_reply_event(dispatcher, agent_name)
            if head is None:
                return None

    reply = dispatcher._message_bureau_control._reply_store.get_latest(reply_id)
    if reply is None:
        return None

    accepted_at = dispatcher._clock()
    project_id = _project_id_for_agent(dispatcher, agent_name)
    if not project_id:
        return None
    spec = dispatcher._registry.spec_for(agent_name)
    runtime = dispatcher._registry.get(agent_name)
    workspace_path = (
        runtime.workspace_path
        if runtime is not None and runtime.workspace_path
        else str(dispatcher._layout.workspace_path(agent_name))
    )
    request = MessageEnvelope(
        project_id=project_id,
        to_agent=agent_name,
        from_actor='system',
        body=_format_reply_delivery_body(dispatcher, reply),
        task_id=f'reply:{reply.reply_id}',
        reply_to=None,
        message_type=_REPLY_DELIVERY_MESSAGE_TYPE,
        delivery_scope=DeliveryScope.SINGLE,
    )
    job_id = dispatcher._new_id('job')
    draft = _JobDraft(
        agent_name=agent_name,
        provider=spec.provider,
        request=request,
        target_kind=TargetKind.AGENT,
        target_name=agent_name,
        provider_options={
            _REPLY_DELIVERY_PROVIDER_OPTION: True,
            _REPLY_DELIVERY_INBOUND_EVENT_OPTION: head.inbound_event_id,
            _REPLY_DELIVERY_REPLY_ID_OPTION: reply.reply_id,
        },
        workspace_path=workspace_path,
    )
    job, status = _build_job_record(
        dispatcher,
        draft,
        job_id=job_id,
        submission_id=None,
        accepted_at=accepted_at,
    )
    _enqueue_submitted_job(dispatcher, job, status=status, accepted_at=accepted_at)

    message_id = dispatcher._new_id('msg')
    attempt_id = dispatcher._new_id('att')
    dispatcher._message_bureau._message_store.append(
        MessageRecord(
            message_id=message_id,
            origin_message_id=reply.message_id,
            from_actor='system',
            target_scope='single',
            target_agents=(agent_name,),
            message_class=_REPLY_DELIVERY_MESSAGE_TYPE,
            reply_policy={'mode': 'none', 'expected_reply_count': 0},
            retry_policy={'mode': 'manual'},
            priority=10,
            payload_ref=f'reply:{reply.reply_id}',
            submission_id=None,
            created_at=accepted_at,
            updated_at=accepted_at,
            message_state=MessageState.QUEUED,
        )
    )
    dispatcher._message_bureau._attempt_store.append(
        AttemptRecord(
            attempt_id=attempt_id,
            message_id=message_id,
            agent_name=agent_name,
            provider=spec.provider,
            job_id=job_id,
            retry_index=0,
            health_snapshot_ref=None,
            started_at=accepted_at,
            updated_at=accepted_at,
            attempt_state=AttemptState.PENDING,
        )
    )
    _rewrite_reply_head(
        dispatcher,
        head,
        reply_id=reply.reply_id,
        delivery_job_id=job_id,
        status=InboundEventStatus.QUEUED,
        updated_at=accepted_at,
        clear_progress=True,
    )
    append_event(
        dispatcher,
        job,
        'reply_delivery_scheduled',
        {
            'inbound_event_id': head.inbound_event_id,
            'reply_id': reply.reply_id,
        },
        timestamp=accepted_at,
    )
    return job


def _head_reply_event(dispatcher, agent_name: str):
    head = dispatcher._message_bureau_control._mailbox_kernel.head_pending_event(agent_name)
    if head is None or head.event_type is not InboundEventType.TASK_REPLY:
        return None
    return head


def _rewrite_reply_head(
    dispatcher,
    current,
    *,
    reply_id: str,
    delivery_job_id: str | None,
    status: InboundEventStatus,
    updated_at: str,
    clear_progress: bool,
) -> None:
    control = dispatcher._message_bureau_control
    updated = InboundEventRecord(
        inbound_event_id=current.inbound_event_id,
        agent_name=current.agent_name,
        event_type=InboundEventType.TASK_REPLY,
        message_id=current.message_id,
        attempt_id=current.attempt_id,
        payload_ref=compose_reply_payload(reply_id, delivery_job_id=delivery_job_id),
        priority=current.priority,
        status=status,
        created_at=current.created_at,
        started_at=None if clear_progress else current.started_at,
        finished_at=None if clear_progress else current.finished_at,
    )
    control._inbound_store.append(updated)
    lease = control._lease_store.load(current.agent_name)
    if lease is not None and lease.inbound_event_id == current.inbound_event_id:
        control._lease_store.remove(current.agent_name)
    control._mailbox_kernel.refresh_mailbox(current.agent_name, updated_at=updated_at)


def _project_id_for_agent(dispatcher, agent_name: str) -> str | None:
    runtime = dispatcher._registry.get(agent_name)
    if runtime is not None and runtime.project_id:
        return runtime.project_id
    latest = dispatcher.latest_for_agent(agent_name)
    if latest is not None and latest.request.project_id:
        return latest.request.project_id
    return None


def _reply_delivery_inbound_event_id(job: JobRecord) -> str | None:
    value = job.provider_options.get(_REPLY_DELIVERY_INBOUND_EVENT_OPTION)
    text = str(value or '').strip()
    return text or None


def _reply_delivery_reply_id(job: JobRecord) -> str | None:
    value = job.provider_options.get(_REPLY_DELIVERY_REPLY_ID_OPTION)
    text = str(value or '').strip()
    return text or None


def _format_reply_delivery_body(dispatcher, reply) -> str:
    attempt = dispatcher._message_bureau_control._attempt_store.get_latest(reply.attempt_id)
    source_job = None
    if attempt is not None:
        source_job = get_job(dispatcher, attempt.job_id)
    if str(reply.diagnostics.get('notice_kind') or '').strip().lower() == 'heartbeat':
        return _format_heartbeat_delivery_body(reply, source_job=source_job)
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


def _format_heartbeat_delivery_body(reply, *, source_job) -> str:
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
        lines[0] = f'{lines[0]} silent_for={_format_silence_seconds(silence_seconds)}'
    body = str(reply.reply or '').strip()
    if body:
        lines.extend(['', body])
    else:
        lines.extend(['', '(empty notice)'])
    return '\n'.join(lines).rstrip()


def _format_silence_seconds(value) -> str:
    try:
        seconds = int(round(float(value)))
    except Exception:
        return str(value)
    return f'{seconds}s'


__all__ = [
    'claim_reply_delivery_start',
    'claimable_reply_delivery_job_ids',
    'is_reply_delivery_job',
    'prepare_reply_deliveries',
    'resolve_reply_delivery_terminal',
]
