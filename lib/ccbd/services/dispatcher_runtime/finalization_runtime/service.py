from __future__ import annotations

from completion.models import CompletionDecision

from ..records import get_job
from ..reply_delivery import prepare_reply_deliveries, resolve_reply_delivery_terminal
from .message_bureau import record_message_bureau_completion
from .persistence import persist_terminal_completion


def complete_job(dispatcher, job_id: str, decision: CompletionDecision):
    if not decision.terminal:
        raise dispatcher._dispatch_error('complete requires a terminal completion decision')
    current = get_job(dispatcher, job_id)
    if current is None:
        raise dispatcher._dispatch_error(f'unknown job: {job_id}')
    if current.status in dispatcher._terminal_event_by_status:
        return current

    finished_at = decision.finished_at or dispatcher._clock()
    terminal, decision, prior_snapshot = persist_terminal_completion(
        dispatcher,
        current,
        decision,
        finished_at=finished_at,
    )
    terminal, _reply_decision, retry_scheduled = record_message_bureau_completion(
        dispatcher,
        current,
        terminal,
        decision,
        finished_at=finished_at,
        prior_snapshot=prior_snapshot,
    )
    resolve_reply_delivery_terminal(dispatcher, terminal, finished_at=finished_at)
    if retry_scheduled:
        return terminal
    if bool(getattr(dispatcher, '_auto_reply_delivery_on_complete', False)):
        prepare_reply_deliveries(dispatcher)
    return terminal


__all__ = ['complete_job']
