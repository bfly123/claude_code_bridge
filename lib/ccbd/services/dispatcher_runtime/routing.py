from __future__ import annotations

from typing import Iterable

from agents.models import AgentState, QueuePolicy, normalize_agent_name
from ccbd.api_models import DeliveryScope

from mailbox_targets import COMMAND_MAILBOX_ACTOR

from .records import get_job, latest_for_agent

_EXTERNAL_ACTORS = frozenset({'user', 'system', 'manual'})


def validate_sender(dispatcher, sender: str) -> None:
    normalized = str(sender or '').strip().lower()
    if not normalized:
        raise dispatcher._dispatch_error('sender cannot be empty')
    if normalized in _EXTERNAL_ACTORS:
        return
    if normalized == COMMAND_MAILBOX_ACTOR:
        return
    agent_name = normalize_agent_name(normalized)
    if agent_name not in dispatcher._config.agents:
        raise dispatcher._dispatch_error(f'unknown sender agent: {agent_name}')


def resolve_targets(dispatcher, request) -> tuple[str, ...]:
    if request.delivery_scope is DeliveryScope.SINGLE:
        dispatcher._registry.spec_for(request.to_agent)
        runtime = dispatcher._registry.get(request.to_agent)
        if runtime is None or runtime.state in {AgentState.STOPPED, AgentState.FAILED}:
            if dispatcher._runtime_service is None:
                raise dispatcher._dispatch_error(f'agent {request.to_agent} is not running')
            dispatcher._runtime_service.ensure_ready(request.to_agent)
        return (request.to_agent,)

    alive = [runtime.agent_name for runtime in dispatcher._registry.list_alive()]
    if request.from_actor not in {'user', 'system'}:
        alive = [name for name in alive if name != request.from_actor]
    return tuple(sorted(alive))


def validate_targets_available(dispatcher, targets: Iterable[str]) -> None:
    for agent_name in targets:
        spec = dispatcher._registry.spec_for(agent_name)
        if spec.queue_policy is QueuePolicy.REJECT_WHEN_BUSY and dispatcher._has_outstanding_work(agent_name):
            raise dispatcher._dispatch_rejected_error(f'agent {agent_name} rejects new work while busy')


def resolve_watch_target(dispatcher, target: str) -> tuple[str, str]:
    normalized = target.strip().lower()
    if not normalized:
        raise dispatcher._dispatch_error('watch target cannot be empty')
    if normalized.startswith('job_'):
        record = get_job(dispatcher, normalized)
        if record is None:
            raise dispatcher._dispatch_error(f'unknown job: {normalized}')
        return record.target_name, record.job_id

    dispatcher._registry.spec_for(normalized)
    active_job_id = dispatcher._state.active_job(normalized)
    if active_job_id is not None:
        return normalized, active_job_id
    latest = latest_for_agent(dispatcher, normalized)
    if latest is None:
        raise dispatcher._dispatch_error(f'agent {normalized} has no jobs to watch')
    return normalized, latest.job_id


def build_watch_payload(dispatcher, target: str, *, start_line: int = 0) -> dict:
    target_name, job_id = resolve_watch_target(dispatcher, target)
    latest = get_job(dispatcher, job_id)
    if latest is None:
        raise dispatcher._dispatch_error(f'unknown job: {job_id}')
    cursor, events = dispatcher._event_store.read_since_target(latest.target_kind, target_name, start_line)
    filtered = [event for event in events if event.job_id == job_id]
    snapshot = dispatcher._snapshot_writer.load(job_id)
    terminal = False
    if latest.status in dispatcher._terminal_event_by_status:
        terminal = True
    return {
        'target': target,
        'job_id': job_id,
        'agent_name': latest.agent_name,
        'target_kind': latest.target_kind.value,
        'target_name': latest.target_name,
        'provider': latest.provider,
        'provider_instance': latest.provider_instance,
        'cursor': cursor,
        'terminal': terminal,
        'status': latest.status.value,
        'reply': snapshot.latest_decision.reply if snapshot is not None else '',
        'events': [event.to_record() for event in filtered],
    }
