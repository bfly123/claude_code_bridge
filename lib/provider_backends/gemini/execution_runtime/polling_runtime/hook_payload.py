from __future__ import annotations

from completion.models import CompletionStatus


def hook_event_diagnostics(event: dict[str, object]) -> dict[str, object]:
    diagnostics = dict(event.get('diagnostics') or {})
    diagnostics.setdefault('completion_source', 'hook_artifact')
    hook_event_name = event.get('hook_event_name')
    if hook_event_name is not None:
        diagnostics.setdefault('hook_event_name', hook_event_name)
    return diagnostics


def hook_decision_reason(status: CompletionStatus, diagnostics: dict[str, object]) -> str:
    explicit_reason = str(diagnostics.get('reason') or '').strip().lower()
    if explicit_reason:
        return explicit_reason
    if status is CompletionStatus.FAILED:
        if failure_diagnostics_present(diagnostics):
            return 'api_error'
        return 'hook_after_agent_failure'
    if status is CompletionStatus.CANCELLED:
        return 'hook_after_agent_cancelled'
    if status is CompletionStatus.INCOMPLETE:
        return 'hook_after_agent_incomplete'
    return 'hook_after_agent'


def hook_item_payload(
    *,
    req_id: str,
    reply: str,
    status: CompletionStatus,
    provider_turn_ref: str,
    hook_event_name: object,
    diagnostics: dict[str, object],
) -> dict[str, object]:
    payload: dict[str, object] = {
        'reply': reply,
        'text': reply,
        'turn_id': req_id,
        'provider_turn_ref': provider_turn_ref,
        'completion_source': 'hook_artifact',
        'hook_event_name': hook_event_name,
        'status': status.value,
    }
    if not payload['text']:
        fallback_text = fallback_payload_text(diagnostics)
        if fallback_text:
            payload['text'] = fallback_text
    for key, value in diagnostics.items():
        if value is None or key in payload:
            continue
        payload[key] = value
    return payload


def failure_diagnostics_present(diagnostics: dict[str, object]) -> bool:
    keys = ('error_type', 'error_code', 'error_message', 'error', 'message', 'text')
    return any(str(diagnostics.get(key) or '').strip() for key in keys)


def fallback_payload_text(diagnostics: dict[str, object]) -> str:
    for key in ('text', 'error_message', 'message', 'error'):
        text = str(diagnostics.get(key) or '').strip()
        if text:
            return text
    return ''


__all__ = ['hook_decision_reason', 'hook_event_diagnostics', 'hook_item_payload']
