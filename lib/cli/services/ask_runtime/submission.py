from __future__ import annotations

from collections.abc import Callable, Collection

from agents.models import AgentValidationError
from ccbd.api_models import DeliveryScope, MessageEnvelope
from mailbox_runtime.targets import CMD_ACTOR, NON_AGENT_ACTORS, normalize_actor_name

from .models import AskSummary


def submit_ask(
    context,
    command,
    *,
    load_project_config_fn: Callable,
    resolve_ask_sender_fn: Callable,
    connect_mounted_daemon_fn: Callable,
) -> AskSummary:
    config = load_project_config_fn(context.project.project_root).config
    normalized_target = _normalize_target(command.target)
    _validate_target(normalized_target, config.agents)
    sender = resolve_ask_sender_fn(context, command.sender)
    normalized_sender = _normalize_sender(sender)
    _validate_sender(normalized_sender, config.agents, cmd_enabled=bool(getattr(config, 'cmd_enabled', False)))
    handle = connect_mounted_daemon_fn(context, allow_restart_stale=True)
    assert handle.client is not None
    payload = handle.client.submit(
        MessageEnvelope(
            project_id=context.project.project_id,
            to_agent=normalized_target,
            from_actor=normalized_sender,
            body=command.message,
            task_id=command.task_id,
            reply_to=command.reply_to,
            message_type=command.mode or 'ask',
            delivery_scope=_delivery_scope(command.target),
            silence_on_success=command.silence,
        )
    )
    return _summary_from_payload(context.project.project_id, payload)


def _normalize_sender(value: str | None) -> str:
    try:
        return normalize_actor_name(value)
    except AgentValidationError as exc:
        raise ValueError(str(exc)) from exc


def _normalize_target(value: str | None) -> str:
    normalized = str(value or '').strip().lower()
    if normalized == 'all':
        return normalized
    return _normalize_sender(normalized)


def _validate_target(target: str, configured_agents: Collection[str]) -> None:
    if target != 'all' and target not in configured_agents:
        raise ValueError(f'unknown agent: {target}')


def _validate_sender(sender: str, configured_agents: Collection[str], *, cmd_enabled: bool) -> None:
    if sender in NON_AGENT_ACTORS:
        if sender == CMD_ACTOR and not cmd_enabled:
            raise ValueError(f'unknown sender agent: {sender}')
        return
    if sender in configured_agents:
        return
    raise ValueError(f'unknown sender agent: {sender}')


def _delivery_scope(target: str | None) -> DeliveryScope:
    return DeliveryScope.BROADCAST if _normalize_target(target) == 'all' else DeliveryScope.SINGLE


def _summary_from_payload(project_id: str, payload: dict) -> AskSummary:
    if 'job_id' in payload:
        jobs = (
            {
                'job_id': payload['job_id'],
                'agent_name': payload['agent_name'],
                'target_kind': payload.get('target_kind', 'agent'),
                'target_name': payload.get('target_name', payload['agent_name']),
                'provider_instance': payload.get('provider_instance'),
                'status': payload['status'],
            },
        )
        submission_id = None
    else:
        jobs = tuple(payload.get('jobs', ()))
        submission_id = payload.get('submission_id')
    return AskSummary(project_id=project_id, submission_id=submission_id, jobs=jobs)


__all__ = ['submit_ask']
