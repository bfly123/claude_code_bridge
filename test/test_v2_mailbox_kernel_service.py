from __future__ import annotations

from pathlib import Path

from mailbox_kernel import (
    DeliveryLeaseStore,
    InboundEventRecord,
    InboundEventStatus,
    InboundEventStore,
    InboundEventType,
    MailboxKernelService,
    MailboxState,
    MailboxStore,
)
from storage.paths import PathLayout


def test_mailbox_kernel_claim_and_consume_updates_mailbox_and_lease(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    inbound_store = InboundEventStore(layout)
    mailbox_store = MailboxStore(layout)
    lease_store = DeliveryLeaseStore(layout)
    service = MailboxKernelService(
        layout,
        clock=lambda: '2026-03-30T10:00:00Z',
        inbound_store=inbound_store,
        mailbox_store=mailbox_store,
        lease_store=lease_store,
    )

    inbound_store.append(
        InboundEventRecord(
            inbound_event_id='evt-task',
            agent_name='agent1',
            event_type=InboundEventType.TASK_REQUEST,
            message_id='msg-1',
            attempt_id='att-1',
            payload_ref='job:job-1',
            priority=100,
            status=InboundEventStatus.QUEUED,
            created_at='2026-03-30T10:00:00Z',
        )
    )
    inbound_store.append(
        InboundEventRecord(
            inbound_event_id='evt-reply',
            agent_name='agent1',
            event_type=InboundEventType.TASK_REPLY,
            message_id='msg-2',
            attempt_id='att-2',
            payload_ref='reply:rep-2',
            priority=10,
            status=InboundEventStatus.QUEUED,
            created_at='2026-03-30T10:00:01Z',
        )
    )

    claimed = service.claim_next('agent1', event_type=InboundEventType.TASK_REQUEST, started_at='2026-03-30T10:00:05Z')

    assert claimed is not None
    assert claimed.inbound_event_id == 'evt-task'
    assert claimed.status is InboundEventStatus.DELIVERING
    lease = lease_store.load('agent1')
    assert lease is not None
    assert lease.inbound_event_id == 'evt-task'
    mailbox = mailbox_store.load('agent1')
    assert mailbox is not None
    assert mailbox.mailbox_state is MailboxState.DELIVERING
    assert mailbox.active_inbound_event_id == 'evt-task'
    assert mailbox.queue_depth == 2
    assert mailbox.pending_reply_count == 1

    consumed = service.consume('agent1', 'evt-task', finished_at='2026-03-30T10:00:10Z')

    assert consumed is not None
    assert consumed.status is InboundEventStatus.CONSUMED
    assert lease_store.load('agent1') is None
    mailbox = mailbox_store.load('agent1')
    assert mailbox is not None
    assert mailbox.mailbox_state is MailboxState.BLOCKED
    assert mailbox.active_inbound_event_id is None
    assert mailbox.queue_depth == 1
    assert mailbox.pending_reply_count == 1


def test_mailbox_kernel_rejects_second_claim_while_other_event_is_active(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    inbound_store = InboundEventStore(layout)
    service = MailboxKernelService(layout, clock=lambda: '2026-03-30T10:00:00Z', inbound_store=inbound_store)

    inbound_store.append(
        InboundEventRecord(
            inbound_event_id='evt-1',
            agent_name='agent1',
            event_type=InboundEventType.TASK_REQUEST,
            message_id='msg-1',
            attempt_id='att-1',
            payload_ref='job:job-1',
            priority=100,
            status=InboundEventStatus.QUEUED,
            created_at='2026-03-30T10:00:00Z',
        )
    )
    inbound_store.append(
        InboundEventRecord(
            inbound_event_id='evt-2',
            agent_name='agent1',
            event_type=InboundEventType.TASK_REQUEST,
            message_id='msg-2',
            attempt_id='att-2',
            payload_ref='job:job-2',
            priority=100,
            status=InboundEventStatus.QUEUED,
            created_at='2026-03-30T10:00:01Z',
        )
    )

    first = service.claim_next('agent1', event_type=InboundEventType.TASK_REQUEST, started_at='2026-03-30T10:00:05Z')
    second = service.claim('agent1', 'evt-2', started_at='2026-03-30T10:00:06Z')

    assert first is not None
    assert second is None
    mailbox = MailboxStore(layout).load('agent1')
    assert mailbox is not None
    assert mailbox.mailbox_state is MailboxState.DELIVERING
    assert mailbox.active_inbound_event_id == 'evt-1'


def test_mailbox_kernel_ack_reply_claims_and_consumes_head_reply(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    inbound_store = InboundEventStore(layout)
    mailbox_store = MailboxStore(layout)
    lease_store = DeliveryLeaseStore(layout)
    service = MailboxKernelService(
        layout,
        clock=lambda: '2026-03-30T10:00:00Z',
        inbound_store=inbound_store,
        mailbox_store=mailbox_store,
        lease_store=lease_store,
    )

    inbound_store.append(
        InboundEventRecord(
            inbound_event_id='evt-reply',
            agent_name='agent1',
            event_type=InboundEventType.TASK_REPLY,
            message_id='msg-1',
            attempt_id='att-1',
            payload_ref='reply:rep-1',
            priority=10,
            status=InboundEventStatus.QUEUED,
            created_at='2026-03-30T10:00:00Z',
        )
    )
    inbound_store.append(
        InboundEventRecord(
            inbound_event_id='evt-task',
            agent_name='agent1',
            event_type=InboundEventType.TASK_REQUEST,
            message_id='msg-2',
            attempt_id='att-2',
            payload_ref='job:job-2',
            priority=100,
            status=InboundEventStatus.QUEUED,
            created_at='2026-03-30T10:00:01Z',
        )
    )

    consumed = service.ack_reply(
        'agent1',
        'evt-reply',
        started_at='2026-03-30T10:00:05Z',
        finished_at='2026-03-30T10:00:05Z',
    )

    assert consumed is not None
    assert consumed.inbound_event_id == 'evt-reply'
    assert consumed.status is InboundEventStatus.CONSUMED
    current = inbound_store.get_latest('agent1', 'evt-reply')
    assert current is not None
    assert current.started_at == '2026-03-30T10:00:05Z'
    assert current.finished_at == '2026-03-30T10:00:05Z'
    assert lease_store.load('agent1') is None
    mailbox = mailbox_store.load('agent1')
    assert mailbox is not None
    assert mailbox.mailbox_state is MailboxState.BLOCKED
    assert mailbox.queue_depth == 1
    assert mailbox.pending_reply_count == 0


def test_mailbox_kernel_supports_command_mailbox_ack_flow(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    inbound_store = InboundEventStore(layout)
    mailbox_store = MailboxStore(layout)
    lease_store = DeliveryLeaseStore(layout)
    service = MailboxKernelService(
        layout,
        clock=lambda: '2026-03-30T10:00:00Z',
        inbound_store=inbound_store,
        mailbox_store=mailbox_store,
        lease_store=lease_store,
    )

    inbound_store.append(
        InboundEventRecord(
            inbound_event_id='evt-cmd-reply',
            agent_name='cmd',
            event_type=InboundEventType.TASK_REPLY,
            message_id='msg-cmd',
            attempt_id='att-cmd',
            payload_ref='reply:rep-cmd',
            priority=10,
            status=InboundEventStatus.QUEUED,
            created_at='2026-03-30T10:00:00Z',
        )
    )

    consumed = service.ack_reply(
        'cmd',
        'evt-cmd-reply',
        started_at='2026-03-30T10:00:05Z',
        finished_at='2026-03-30T10:00:05Z',
    )

    assert consumed is not None
    assert consumed.agent_name == 'cmd'
    mailbox = mailbox_store.load('cmd')
    assert mailbox is not None
    assert mailbox.mailbox_state is MailboxState.IDLE
    assert mailbox.queue_depth == 0
