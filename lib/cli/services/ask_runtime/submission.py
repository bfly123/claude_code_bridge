from __future__ import annotations

from collections.abc import Callable, Collection

from ccbd.api_models import DeliveryScope, MessageEnvelope

from .models import AskSummary


_SYSTEM_SENDERS = {'user', 'system', 'manual'}


def submit_ask(
    context,
    command,
    *,
    load_project_config_fn: Callable,
    resolve_ask_sender_fn: Callable,
    connect_mounted_daemon_fn: Callable,
    command_mailbox_actor: str,
) -> AskSummary:
    config = load_project_config_fn(context.project.project_root).config
    normalized_target = _normalize_actor(command.target)
    _validate_target(normalized_target, config.agents)
    sender = resolve_ask_sender_fn(context, command.sender)
    normalized_sender = _normalize_actor(sender)
    _validate_sender(normalized_sender, config.agents, command_mailbox_actor)
    handle = connect_mounted_daemon_fn(context, allow_restart_stale=True)
    assert handle.client is not None
    payload = handle.client.submit(
        MessageEnvelope(
            project_id=context.project.project_id,
            to_agent=normalized_target,
            from_actor=sender,
            body=command.message,
            task_id=command.task_id,
            reply_to=command.reply_to,
            message_type=command.mode or 'ask',
            delivery_scope=_delivery_scope(command.target),
            silence_on_success=command.silence,
        )
    )
    return _summary_from_payload(context.project.project_id, payload)


def _normalize_actor(value: str | None) -> str:
    return str(value or '').strip().lower()


def _validate_target(target: str, configured_agents: Collection[str]) -> None:
    if target != 'all' and target not in configured_agents:
        raise ValueError(f'unknown agent: {target}')


def _validate_sender(sender: str, configured_agents: Collection[str], command_mailbox_actor: str) -> None:
    if sender in _SYSTEM_SENDERS or sender == command_mailbox_actor:
        return
    if sender in configured_agents:
        return
    raise ValueError(f'unknown sender agent: {sender}')


def _delivery_scope(target: str | None) -> DeliveryScope:
    return DeliveryScope.BROADCAST if _normalize_actor(target) == 'all' else DeliveryScope.SINGLE


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
