from __future__ import annotations

from types import SimpleNamespace

from mailbox_kernel import InboundEventRecord, InboundEventStatus, InboundEventType, MailboxRecord, MailboxState
from message_bureau.control_queue import ack_reply, agent_queue, queue_summary
from message_bureau.models import AttemptRecord, AttemptState, MessageRecord, MessageState, ReplyRecord, ReplyTerminalStatus
from message_bureau.reply_payloads import compose_reply_payload


class _MailboxStore:
    def __init__(self, records: dict[str, object | None]) -> None:
        self._records = records

    def load(self, agent_name: str):
        return self._records.get(agent_name)


class _InboundStore:
    def __init__(self, records: dict[str, list[object]]) -> None:
        self._records = records

    def list_agent(self, agent_name: str):
        return list(self._records.get(agent_name, ()))


class _SingleStore:
    def __init__(self, records: dict[str, object], *, list_records: dict[str, list[object]] | None = None) -> None:
        self._records = records
        self._list_records = list_records or {}

    def get_latest(self, record_id: str):
        return self._records.get(record_id)

    def list_message(self, message_id: str):
        return list(self._list_records.get(message_id, ()))


class _MailboxKernel:
    def __init__(self, head, *, next_head=None) -> None:
        self._head = head
        self._next_head = next_head
        self._acked = False

    def head_pending_event(self, agent_name: str):
        del agent_name
        if self._acked:
            return self._next_head
        return self._head

    def ack_reply(self, agent_name: str, inbound_event_id: str, *, started_at: str, finished_at: str):
        del agent_name, inbound_event_id, started_at, finished_at
        self._acked = True
        return self._head


def _service(*, mailbox_store, inbound_store, attempt_store, message_store, reply_store, mailbox_kernel):
    return SimpleNamespace(
        _known_mailboxes={'agent1'},
        _config=SimpleNamespace(agents={'agent1': object()}),
        _clock=lambda: '2026-04-05T00:00:00Z',
        _mailbox_store=mailbox_store,
        _inbound_store=inbound_store,
        _attempt_store=attempt_store,
        _message_store=message_store,
        _reply_store=reply_store,
        _mailbox_kernel=mailbox_kernel,
    )


def test_agent_queue_derives_delivering_state_without_mailbox_record() -> None:
    event = InboundEventRecord(
        inbound_event_id='iev_1',
        agent_name='agent1',
        event_type=InboundEventType.TASK_REQUEST,
        message_id='msg_1',
        attempt_id='att_1',
        payload_ref=None,
        priority=10,
        status=InboundEventStatus.DELIVERING,
        created_at='2026-04-05T00:00:00Z',
    )
    attempt = AttemptRecord(
        attempt_id='att_1',
        message_id='msg_1',
        agent_name='agent1',
        provider='codex',
        job_id='job_1',
        retry_index=0,
        health_snapshot_ref=None,
        started_at='2026-04-05T00:00:00Z',
        updated_at='2026-04-05T00:00:00Z',
        attempt_state=AttemptState.RUNNING,
    )
    message = MessageRecord(
        message_id='msg_1',
        origin_message_id=None,
        from_actor='user',
        target_scope='single',
        target_agents=('agent1',),
        created_at='2026-04-05T00:00:00Z',
        updated_at='2026-04-05T00:00:00Z',
        message_state=MessageState.RUNNING,
    )
    service = _service(
        mailbox_store=_MailboxStore({'agent1': None}),
        inbound_store=_InboundStore({'agent1': [event]}),
        attempt_store=_SingleStore({'att_1': attempt}),
        message_store=_SingleStore({'msg_1': message}),
        reply_store=_SingleStore({}, list_records={'msg_1': []}),
        mailbox_kernel=_MailboxKernel(event),
    )

    payload = agent_queue(service, 'agent1')

    assert payload['mailbox_state'] == MailboxState.DELIVERING.value
    assert payload['active_inbound_event_id'] == 'iev_1'
    assert payload['queue_depth'] == 1


def test_queue_summary_ignores_stale_cmd_residue() -> None:
    service = _service(
        mailbox_store=_MailboxStore(
            {
                'agent1': None,
                'cmd': SimpleNamespace(
                    mailbox_id='mbx_cmd',
                    agent_name='cmd',
                    active_inbound_event_id=None,
                    queue_depth=1,
                    pending_reply_count=0,
                    last_inbound_started_at=None,
                    last_inbound_finished_at=None,
                    mailbox_state=MailboxState.BLOCKED,
                    lease_version=3,
                    updated_at='2026-04-05T00:00:00Z',
                ),
            }
        ),
        inbound_store=_InboundStore({'agent1': [], 'cmd': [SimpleNamespace(inbound_event_id='iev_cmd')]}),
        attempt_store=_SingleStore({}),
        message_store=_SingleStore({}),
        reply_store=_SingleStore({}),
        mailbox_kernel=_MailboxKernel(None),
    )

    payload = queue_summary(service, 'all')

    assert payload['agent_count'] == 1
    assert {item['agent_name'] for item in payload['agents']} == {'agent1'}
    assert payload['total_queue_depth'] == 0


def test_ack_reply_returns_reply_metadata_and_next_head() -> None:
    head = InboundEventRecord(
        inbound_event_id='iev_reply_1',
        agent_name='agent1',
        event_type=InboundEventType.TASK_REPLY,
        message_id='msg_1',
        attempt_id='att_1',
        payload_ref=compose_reply_payload('rep_1'),
        priority=5,
        status=InboundEventStatus.DELIVERING,
        created_at='2026-04-05T00:00:00Z',
    )
    next_head = InboundEventRecord(
        inbound_event_id='iev_reply_2',
        agent_name='agent1',
        event_type=InboundEventType.TASK_REQUEST,
        message_id='msg_2',
        attempt_id='att_2',
        payload_ref=None,
        priority=6,
        status=InboundEventStatus.QUEUED,
        created_at='2026-04-05T00:01:00Z',
    )
    attempt = AttemptRecord(
        attempt_id='att_1',
        message_id='msg_1',
        agent_name='agent1',
        provider='codex',
        job_id='job_1',
        retry_index=0,
        health_snapshot_ref=None,
        started_at='2026-04-05T00:00:00Z',
        updated_at='2026-04-05T00:00:00Z',
        attempt_state=AttemptState.REPLY_READY,
    )
    message = MessageRecord(
        message_id='msg_1',
        origin_message_id=None,
        from_actor='agent2',
        target_scope='single',
        target_agents=('agent1',),
        created_at='2026-04-05T00:00:00Z',
        updated_at='2026-04-05T00:00:00Z',
        message_state=MessageState.COMPLETED,
    )
    reply = ReplyRecord(
        reply_id='rep_1',
        message_id='msg_1',
        attempt_id='att_1',
        agent_name='agent2',
        terminal_status=ReplyTerminalStatus.COMPLETED,
        reply='done',
        diagnostics={'notice': True, 'notice_kind': 'heartbeat', 'last_progress_at': '2026-04-05T00:00:30Z'},
        finished_at='2026-04-05T00:00:40Z',
    )
    service = _service(
        mailbox_store=_MailboxStore({'agent1': MailboxRecord(
            mailbox_id='mbx_agent1',
            agent_name='agent1',
            active_inbound_event_id='iev_reply_2',
            queue_depth=1,
            pending_reply_count=0,
            last_inbound_started_at='2026-04-05T00:01:00Z',
            last_inbound_finished_at=None,
            mailbox_state=MailboxState.DELIVERING,
            lease_version=4,
            updated_at='2026-04-05T00:01:00Z',
        )}),
        inbound_store=_InboundStore({'agent1': [next_head]}),
        attempt_store=_SingleStore({'att_1': attempt, 'att_2': attempt}),
        message_store=_SingleStore({'msg_1': message, 'msg_2': message}),
        reply_store=_SingleStore({'rep_1': reply}, list_records={'msg_2': [], 'msg_1': [reply]}),
        mailbox_kernel=_MailboxKernel(head, next_head=next_head),
    )

    payload = ack_reply(service, 'agent1')

    assert payload['acknowledged_inbound_event_id'] == 'iev_reply_1'
    assert payload['job_id'] == 'job_1'
    assert payload['reply_id'] == 'rep_1'
    assert payload['reply_notice_kind'] == 'heartbeat'
    assert payload['next_inbound_event_id'] == 'iev_reply_2'
    assert payload['reply'] == 'done'
