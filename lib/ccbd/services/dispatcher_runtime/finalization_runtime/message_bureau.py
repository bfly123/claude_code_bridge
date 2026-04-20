from __future__ import annotations

from completion.models import CompletionDecision

from ..reply_delivery import is_reply_delivery_job
from .message_bureau_persistence import persist_reply_decision
from .message_bureau_retry import reply_decision_without_automatic_retry, schedule_automatic_retry


def record_message_bureau_completion(
    dispatcher,
    current,
    terminal,
    decision: CompletionDecision,
    *,
    finished_at: str,
    prior_snapshot,
) -> tuple[object, CompletionDecision, bool]:
    reply_decision = decision
    if dispatcher._message_bureau is None:
        return terminal, reply_decision, False

    dispatcher._message_bureau.record_attempt_terminal(terminal, decision, finished_at=finished_at)
    if is_reply_delivery_job(current):
        return terminal, reply_decision, False
    reply_decision, retry_scheduled = schedule_automatic_retry(
        dispatcher,
        current,
        terminal,
        decision,
        finished_at=finished_at,
    )
    if retry_scheduled:
        return terminal, decision, True
    if reply_decision is decision:
        reply_decision = reply_decision_without_automatic_retry(
            dispatcher,
            current,
            terminal,
            decision,
            finished_at=finished_at,
        )
    if reply_decision is not decision:
        terminal = persist_reply_decision(
            dispatcher,
            current,
            terminal,
            reply_decision,
            prior_snapshot=prior_snapshot,
            finished_at=finished_at,
        )
    dispatcher._message_bureau.record_reply(terminal, reply_decision, finished_at=finished_at)
    return terminal, reply_decision, False


__all__ = ['record_message_bureau_completion']
