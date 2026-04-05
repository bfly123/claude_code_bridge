from __future__ import annotations

from agents.models import AgentState
from ccbd.api_models import DeliveryScope, JobRecord, MessageEnvelope, TargetKind
from message_bureau import AttemptState, AttemptStore, MessageStore

from .submission_models import _JobDraft, _message_for_agent, _SubmissionPlan
from .submission_recording import _append_submission_job, _build_job_record, _enqueue_submitted_job, _submit_plan

_TERMINAL_ATTEMPT_STATES = frozenset(
    {
        AttemptState.COMPLETED,
        AttemptState.INCOMPLETE,
        AttemptState.FAILED,
        AttemptState.CANCELLED,
        AttemptState.SUPERSEDED,
        AttemptState.DEAD_LETTER,
    }
)


def _plan_agent_submission(dispatcher, request: MessageEnvelope) -> _SubmissionPlan:
    dispatcher._validate_sender(request.from_actor)
    targets = dispatcher._resolve_targets(request)
    if not targets:
        raise dispatcher._dispatch_error('no eligible target agents are alive for this request')
    dispatcher._validate_targets_available(targets)
    submission_id = dispatcher._new_id('sub') if request.delivery_scope is DeliveryScope.BROADCAST else None
    drafts = []
    for agent_name in targets:
        spec = dispatcher._registry.spec_for(agent_name)
        drafts.append(
            _JobDraft(
                agent_name=agent_name,
                provider=spec.provider,
                request=_message_for_agent(request, agent_name=agent_name),
                target_kind=TargetKind.AGENT,
                target_name=agent_name,
            )
        )
    return _SubmissionPlan(
        project_id=request.project_id,
        from_actor=request.from_actor,
        request=request,
        task_id=request.task_id,
        drafts=tuple(drafts),
        submission_id=submission_id,
        target_scope='all' if submission_id is not None else None,
    )


def _plan_message_resubmission(dispatcher, message_id: str) -> _SubmissionPlan:
    original_message = MessageStore(dispatcher._layout).get_latest(message_id)
    if original_message is None:
        raise dispatcher._dispatch_error(f'message not found: {message_id}')

    latest_attempts = _latest_attempts_by_agent(dispatcher, message_id)
    if not latest_attempts:
        raise dispatcher._dispatch_error(f'message has no attempts to resubmit: {message_id}')
    missing_agents = [agent_name for agent_name in original_message.target_agents if agent_name not in latest_attempts]
    if missing_agents:
        raise dispatcher._dispatch_error(f'message is missing attempt lineage for agents: {", ".join(missing_agents)}')
    active_agents = sorted(
        agent_name
        for agent_name, attempt in latest_attempts.items()
        if attempt.attempt_state not in _TERMINAL_ATTEMPT_STATES
    )
    if active_agents:
        raise dispatcher._dispatch_error(f'message still has active attempts: {", ".join(active_agents)}')

    jobs: list[JobRecord] = []
    for agent_name in original_message.target_agents:
        _ensure_agent_target_ready(dispatcher, agent_name)
        attempt = latest_attempts[agent_name]
        job = dispatcher._job_store.get_latest(agent_name, attempt.job_id)
        if job is None:
            raise dispatcher._dispatch_error(f'job not found for attempt: {attempt.attempt_id}')
        jobs.append(job)

    source = jobs[0].request
    delivery_scope = DeliveryScope.BROADCAST if len(original_message.target_agents) > 1 else DeliveryScope.SINGLE
    request = MessageEnvelope(
        project_id=source.project_id,
        to_agent='all' if delivery_scope is DeliveryScope.BROADCAST else original_message.target_agents[0],
        from_actor=original_message.from_actor,
        body=source.body,
        task_id=source.task_id,
        reply_to=source.reply_to,
        message_type=source.message_type,
        delivery_scope=delivery_scope,
        silence_on_success=source.silence_on_success,
    )
    dispatcher._validate_sender(request.from_actor)
    dispatcher._validate_targets_available(original_message.target_agents)

    drafts = []
    for agent_name in original_message.target_agents:
        spec = dispatcher._registry.spec_for(agent_name)
        drafts.append(
            _JobDraft(
                agent_name=agent_name,
                provider=spec.provider,
                request=_message_for_agent(request, agent_name=agent_name),
                target_kind=TargetKind.AGENT,
                target_name=agent_name,
            )
        )
    submission_id = dispatcher._new_id('sub') if delivery_scope is DeliveryScope.BROADCAST else None
    return _SubmissionPlan(
        project_id=request.project_id,
        from_actor=request.from_actor,
        request=request,
        task_id=request.task_id,
        drafts=tuple(drafts),
        submission_id=submission_id,
        target_scope='all' if submission_id is not None else None,
        origin_message_id=message_id,
    )


def _resolve_retry_attempt(dispatcher, target: str):
    attempt_store = AttemptStore(dispatcher._layout)
    attempt = attempt_store.get_latest(target)
    if attempt is not None:
        return attempt
    attempt = attempt_store.get_latest_by_job_id(target)
    if attempt is not None:
        return attempt
    raise dispatcher._dispatch_error(f'retry target not found: {target}')


def _latest_attempts_by_agent(dispatcher, message_id: str) -> dict[str, object]:
    attempt_store = AttemptStore(dispatcher._layout)
    latest_by_attempt_id: dict[str, object] = {}
    for record in attempt_store.list_message(message_id):
        latest_by_attempt_id[record.attempt_id] = record
    latest_by_agent: dict[str, object] = {}
    for record in latest_by_attempt_id.values():
        current = latest_by_agent.get(record.agent_name)
        if current is None or (record.retry_index, record.updated_at, record.attempt_id) > (
            current.retry_index,
            current.updated_at,
            current.attempt_id,
        ):
            latest_by_agent[record.agent_name] = record
    return latest_by_agent


def _ensure_agent_target_ready(dispatcher, agent_name: str) -> None:
    dispatcher._registry.spec_for(agent_name)
    runtime = dispatcher._registry.get(agent_name)
    if runtime is None or runtime.state in {AgentState.STOPPED, AgentState.FAILED}:
        if dispatcher._runtime_service is None:
            raise dispatcher._dispatch_error(f'agent {agent_name} is not running')
        dispatcher._runtime_service.ensure_ready(agent_name)


__all__ = [
    '_append_submission_job',
    '_build_job_record',
    '_enqueue_submitted_job',
    '_ensure_agent_target_ready',
    '_JobDraft',
    '_latest_attempts_by_agent',
    '_plan_agent_submission',
    '_plan_message_resubmission',
    '_resolve_retry_attempt',
    '_SubmissionPlan',
    '_submit_plan',
]
