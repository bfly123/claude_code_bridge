from __future__ import annotations

import pytest

from ccbd.api_models import DeliveryScope, JobEvent, JobRecord, JobStatus, MessageEnvelope, SubmissionRecord, TargetKind


def test_message_envelope_validates_delivery_scope() -> None:
    with pytest.raises(ValueError):
        MessageEnvelope(
            project_id='proj',
            to_agent='all',
            from_actor='user',
            body='hello',
            task_id=None,
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )


def test_message_envelope_normalizes_agent_names_and_system_sender() -> None:
    envelope = MessageEnvelope(
        project_id='proj',
        to_agent='Agent1',
        from_actor='System',
        body='hello',
        task_id=None,
        reply_to=None,
        message_type='ask',
        delivery_scope=DeliveryScope.SINGLE,
    )

    assert envelope.to_agent == 'agent1'
    assert envelope.from_actor == 'system'


def test_message_envelope_preserves_cmd_and_email_actors() -> None:
    cmd_envelope = MessageEnvelope(
        project_id='proj',
        to_agent='Agent1',
        from_actor='cmd',
        body='hello',
        task_id=None,
        reply_to=None,
        message_type='ask',
        delivery_scope=DeliveryScope.SINGLE,
    )
    email_envelope = MessageEnvelope(
        project_id='proj',
        to_agent='Agent1',
        from_actor='Email',
        body='hello',
        task_id=None,
        reply_to=None,
        message_type='ask',
        delivery_scope=DeliveryScope.SINGLE,
    )

    assert cmd_envelope.from_actor == 'cmd'
    assert email_envelope.from_actor == 'email'


def test_job_record_requires_terminal_decision_for_terminal_state() -> None:
    envelope = MessageEnvelope(
        project_id='proj',
        to_agent='agent1',
        from_actor='user',
        body='hello',
        task_id=None,
        reply_to=None,
        message_type='ask',
        delivery_scope=DeliveryScope.SINGLE,
    )
    with pytest.raises(ValueError):
        JobRecord(
            job_id='job-1',
            submission_id=None,
            agent_name='agent1',
            provider='codex',
            request=envelope,
            status=JobStatus.COMPLETED,
            terminal_decision=None,
            cancel_requested_at=None,
            created_at='2026-03-18T00:00:00Z',
            updated_at='2026-03-18T00:00:01Z',
        )


def test_records_include_schema_version() -> None:
    envelope = MessageEnvelope(
        project_id='proj',
        to_agent='agent1',
        from_actor='user',
        body='hello',
        task_id='task-1',
        reply_to=None,
        message_type='ask',
        delivery_scope=DeliveryScope.SINGLE,
    )
    job = JobRecord(
        job_id='job-1',
        submission_id=None,
        agent_name='agent1',
        provider='codex',
        request=envelope,
        status=JobStatus.RUNNING,
        terminal_decision=None,
        cancel_requested_at=None,
        created_at='2026-03-18T00:00:00Z',
        updated_at='2026-03-18T00:00:01Z',
    )
    submission = SubmissionRecord(
        submission_id='sub-1',
        project_id='proj',
        from_actor='system',
        target_scope='all',
        task_id='task-1',
        job_ids=['job-1'],
        created_at='2026-03-18T00:00:00Z',
        updated_at='2026-03-18T00:00:01Z',
    )
    event = JobEvent(
        event_id='evt-1',
        job_id='job-1',
        agent_name='agent1',
        type='job_started',
        payload={'status': 'running'},
        timestamp='2026-03-18T00:00:00Z',
    )

    assert job.to_record()['schema_version'] == 2
    assert submission.to_record()['schema_version'] == 2
    assert event.to_record()['schema_version'] == 2


def test_message_envelope_rejects_invalid_sender() -> None:
    with pytest.raises(ValueError):
        MessageEnvelope(
            project_id='proj',
            to_agent='agent1',
            from_actor='invalid sender',
            body='hello',
            task_id=None,
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )


def test_submission_record_preserves_cmd_sender() -> None:
    submission = SubmissionRecord(
        submission_id='sub-1',
        project_id='proj',
        from_actor='CMD',
        target_scope='single',
        task_id=None,
        job_ids=['job-1'],
        created_at='2026-03-18T00:00:00Z',
        updated_at='2026-03-18T00:00:01Z',
    )

    assert submission.from_actor == 'cmd'


def test_job_record_normalizes_agent_target_identity() -> None:
    envelope = MessageEnvelope(
        project_id='proj',
        to_agent='agent1',
        from_actor='user',
        body='hello',
        task_id=None,
        reply_to=None,
        message_type='ask',
        delivery_scope=DeliveryScope.SINGLE,
    )

    job = JobRecord(
        job_id='job-agent-1',
        submission_id=None,
        agent_name='Agent1',
        provider='codex',
        target_kind=TargetKind.AGENT,
        target_name='Agent1',
        request=envelope,
        status=JobStatus.ACCEPTED,
        terminal_decision=None,
        cancel_requested_at=None,
        created_at='2026-03-18T00:00:00Z',
        updated_at='2026-03-18T00:00:01Z',
    )

    record = job.to_record()
    assert job.target_kind is TargetKind.AGENT
    assert job.target_name == 'agent1'
    assert job.provider_instance is None
    assert job.agent_name == 'agent1'
    assert record['target_kind'] == 'agent'
    assert record['target_name'] == 'agent1'
    assert record['provider_instance'] is None


def test_job_event_normalizes_agent_target_identity() -> None:
    event = JobEvent(
        event_id='evt-agent-1',
        job_id='job-agent-1',
        agent_name='Agent1',
        target_kind=TargetKind.AGENT,
        target_name='Agent1',
        type='job_started',
        payload={'status': 'running'},
        timestamp='2026-03-18T00:00:00Z',
    )

    record = event.to_record()
    assert event.target_kind is TargetKind.AGENT
    assert event.target_name == 'agent1'
    assert event.agent_name == 'agent1'
    assert record['target_kind'] == 'agent'
    assert record['target_name'] == 'agent1'
