from __future__ import annotations

from .decisions import reply_delivery_completed_decision, reply_delivery_failed_decision


def complete_reply_delivery_after_start(
    dispatcher,
    job,
    *,
    started_at: str,
    submission,
):
    mode = str((submission.runtime_state if submission is not None else {}).get('mode') or '').strip().lower()
    if submission is None or mode in {'error', 'passive'}:
        diagnostics = {
            'submission_mode': mode or 'missing',
        }
        if submission is not None:
            diagnostics['submission_reason'] = str(submission.runtime_state.get('reason') or submission.reason or '')
            diagnostics['submission_error'] = str(submission.runtime_state.get('error') or '')
        return dispatcher.complete(
            job.job_id,
            reply_delivery_failed_decision(
                job,
                finished_at=started_at,
                reason='reply_delivery_transport_unavailable',
                diagnostics=diagnostics,
            ),
        )

    if bool((submission.runtime_state if submission is not None else {}).get('reply_delivery_complete_on_dispatch', False)):
        return job

    provider_turn_ref = str(
        submission.runtime_state.get('request_anchor')
        or submission.runtime_state.get('pane_id')
        or submission.job_id
    ).strip()
    return dispatcher.complete(
        job.job_id,
        reply_delivery_completed_decision(
            job,
            finished_at=started_at,
            provider_turn_ref=provider_turn_ref or job.job_id,
            diagnostics={
                'submission_mode': mode or 'active',
                'provider': submission.provider,
            },
        ),
    )


__all__ = ['complete_reply_delivery_after_start']
