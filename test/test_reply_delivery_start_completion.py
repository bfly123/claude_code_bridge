from __future__ import annotations

from types import SimpleNamespace

from ccbd.api_models import DeliveryScope, MessageEnvelope, TargetKind
from ccbd.services.dispatcher_runtime.reply_delivery_runtime.start_completion import complete_reply_delivery_after_start
from completion.models import CompletionSourceKind
from provider_execution.base import ProviderSubmission


def _job():
    return SimpleNamespace(
        job_id="job_reply",
        agent_name="agent1",
        provider="claude",
        target_kind=TargetKind.AGENT,
        target_name="agent1",
        request=MessageEnvelope(
            project_id="proj_1",
            to_agent="agent1",
            from_actor="system",
            body="CCB_REPLY from=agent2 reply=rep_1",
            task_id="reply:rep_1",
            reply_to=None,
            message_type="reply_delivery",
            delivery_scope=DeliveryScope.SINGLE,
        ),
    )


def test_complete_reply_delivery_after_start_defers_when_provider_requests_dispatch_completion() -> None:
    job = _job()
    calls: list[tuple[str, object]] = []

    dispatcher = SimpleNamespace(
        complete=lambda job_id, decision: calls.append((job_id, decision)),
    )
    submission = ProviderSubmission(
        job_id=job.job_id,
        agent_name=job.agent_name,
        provider=job.provider,
        accepted_at="2026-04-09T00:00:00Z",
        ready_at="2026-04-09T00:00:00Z",
        source_kind=CompletionSourceKind.SESSION_EVENT_LOG,
        reply="",
        runtime_state={
            "mode": "active",
            "request_anchor": "job_reply",
            "reply_delivery_complete_on_dispatch": True,
        },
    )

    result = complete_reply_delivery_after_start(
        dispatcher,
        job,
        started_at="2026-04-09T00:00:01Z",
        submission=submission,
    )

    assert result is job
    assert calls == []
