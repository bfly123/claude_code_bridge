from __future__ import annotations

from pathlib import Path

import pytest

from mailbox_kernel import (
    DeliveryLease,
    DeliveryLeaseStore,
    InboundEventRecord,
    InboundEventStatus,
    InboundEventStore,
    InboundEventType,
    LeaseState,
    MailboxRecord,
    MailboxState,
    MailboxStore,
)
from storage.paths import PathLayout


def test_mailbox_store_roundtrip(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    store = MailboxStore(layout)

    store.save(
        MailboxRecord(
            mailbox_id='mbx-agent1',
            agent_name='Agent1',
            active_inbound_event_id='evt-1',
            queue_depth=3,
            pending_reply_count=1,
            last_inbound_started_at='2026-03-30T10:00:00Z',
            last_inbound_finished_at='2026-03-30T10:01:00Z',
            mailbox_state=MailboxState.BLOCKED,
            lease_version=4,
            updated_at='2026-03-30T10:01:00Z',
        )
    )

    loaded = store.load('agent1')
    assert loaded is not None
    assert loaded.agent_name == 'agent1'
    assert loaded.mailbox_state is MailboxState.BLOCKED
    assert loaded.queue_depth == 3
    assert [record.agent_name for record in store.list_all()] == ['agent1']


def test_inbound_event_store_supports_queue_history_reads(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    store = InboundEventStore(layout)

    store.append(
        InboundEventRecord(
            inbound_event_id='evt-1',
            agent_name='Agent1',
            event_type=InboundEventType.TASK_REQUEST,
            message_id='msg-1',
            attempt_id='att-1',
            payload_ref='payload://1',
            priority=100,
            status=InboundEventStatus.QUEUED,
            created_at='2026-03-30T10:00:00Z',
        )
    )
    store.append(
        InboundEventRecord(
            inbound_event_id='evt-2',
            agent_name='agent1',
            event_type=InboundEventType.TASK_REPLY,
            message_id='msg-1',
            attempt_id='att-1',
            payload_ref='payload://reply',
            priority=10,
            status=InboundEventStatus.DELIVERING,
            created_at='2026-03-30T10:00:01Z',
            started_at='2026-03-30T10:00:02Z',
        )
    )

    line_no, rows = store.read_since('agent1', 1)
    assert line_no == 2
    assert len(rows) == 1
    assert rows[0].event_type is InboundEventType.TASK_REPLY
    latest = store.get_latest('agent1', 'evt-2')
    assert latest is not None
    assert latest.status is InboundEventStatus.DELIVERING


def test_delivery_lease_store_roundtrip_and_remove(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    store = DeliveryLeaseStore(layout)

    store.save(
        DeliveryLease(
            agent_name='Agent1',
            inbound_event_id='evt-2',
            lease_version=5,
            acquired_at='2026-03-30T10:00:02Z',
            last_progress_at='2026-03-30T10:00:05Z',
            expires_at='2026-03-30T10:01:02Z',
            lease_state=LeaseState.ACQUIRED,
        )
    )

    loaded = store.load('agent1')
    assert loaded is not None
    assert loaded.agent_name == 'agent1'
    assert loaded.lease_state is LeaseState.ACQUIRED
    assert [lease.agent_name for lease in store.list_all()] == ['agent1']

    store.remove('agent1')
    assert store.load('agent1') is None


def test_mailbox_store_rejects_cmd_mailbox_owner(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    mailbox_store = MailboxStore(layout)
    inbound_store = InboundEventStore(layout)
    lease_store = DeliveryLeaseStore(layout)

    with pytest.raises(ValueError, match="actor 'user' does not own a mailbox"):
        mailbox_store.save(
            MailboxRecord(
                mailbox_id='mbx-cmd',
                agent_name='cmd',
                active_inbound_event_id='evt-cmd',
                queue_depth=1,
                pending_reply_count=1,
                last_inbound_started_at='2026-03-30T10:00:00Z',
                last_inbound_finished_at=None,
                mailbox_state=MailboxState.BLOCKED,
                lease_version=1,
                updated_at='2026-03-30T10:00:00Z',
            )
        )

    with pytest.raises(ValueError, match="actor 'user' does not own a mailbox"):
        inbound_store.append(
            InboundEventRecord(
                inbound_event_id='evt-cmd',
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

    with pytest.raises(ValueError, match="actor 'user' does not own a mailbox"):
        lease_store.save(
            DeliveryLease(
                agent_name='cmd',
                inbound_event_id='evt-cmd',
                lease_version=1,
                acquired_at='2026-03-30T10:00:00Z',
                last_progress_at='2026-03-30T10:00:01Z',
                expires_at=None,
                lease_state=LeaseState.ACQUIRED,
            )
        )
