from __future__ import annotations

from pathlib import Path

from message_bureau import (
    AttemptRecord,
    AttemptState,
    AttemptStore,
    MessageRecord,
    MessageState,
    MessageStore,
    ReplyRecord,
    ReplyStore,
    ReplyTerminalStatus,
)
from storage.paths import PathLayout


def test_message_store_tracks_latest_state_per_message(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    store = MessageStore(layout)

    store.append(
        MessageRecord(
            message_id='msg-1',
            origin_message_id=None,
            from_actor='AgentSender',
            target_scope='single',
            target_agents=('Agent1',),
            message_class='task_request',
            reply_policy={'mode': 'one'},
            retry_policy={'mode': 'manual'},
            priority=50,
            payload_ref='payload://msg-1',
            submission_id='sub-1',
            created_at='2026-03-30T11:00:00Z',
            updated_at='2026-03-30T11:00:00Z',
            message_state=MessageState.QUEUED,
        )
    )
    store.append(
        MessageRecord(
            message_id='msg-1',
            origin_message_id=None,
            from_actor='agentsender',
            target_scope='single',
            target_agents=('agent1',),
            message_class='task_request',
            reply_policy={'mode': 'one'},
            retry_policy={'mode': 'manual'},
            priority=50,
            payload_ref='payload://msg-1',
            submission_id='sub-1',
            created_at='2026-03-30T11:00:00Z',
            updated_at='2026-03-30T11:00:03Z',
            message_state=MessageState.RUNNING,
        )
    )

    latest = store.get_latest('msg-1')
    assert latest is not None
    assert latest.from_actor == 'agentsender'
    assert latest.target_agents == ('agent1',)
    assert latest.message_state is MessageState.RUNNING
    assert [record.message_id for record in store.list_submission('sub-1')] == ['msg-1', 'msg-1']


def test_attempt_and_reply_stores_support_message_and_agent_queries(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    attempt_store = AttemptStore(layout)
    reply_store = ReplyStore(layout)

    attempt_store.append(
        AttemptRecord(
            attempt_id='att-1',
            message_id='msg-1',
            agent_name='Agent1',
            provider='codex',
            job_id='job-1',
            retry_index=0,
            health_snapshot_ref='job-1',
            started_at='2026-03-30T11:01:00Z',
            updated_at='2026-03-30T11:01:00Z',
            attempt_state=AttemptState.RUNNING,
        )
    )
    attempt_store.append(
        AttemptRecord(
            attempt_id='att-2',
            message_id='msg-1',
            agent_name='agent1',
            provider='codex',
            job_id='job-2',
            retry_index=1,
            health_snapshot_ref='job-2',
            started_at='2026-03-30T11:02:00Z',
            updated_at='2026-03-30T11:03:00Z',
            attempt_state=AttemptState.COMPLETED,
        )
    )

    reply_store.append(
        ReplyRecord(
            reply_id='rep-1',
            message_id='msg-1',
            attempt_id='att-2',
            agent_name='Agent1',
            terminal_status=ReplyTerminalStatus.COMPLETED,
            reply='done',
            diagnostics={'tokens': 12},
            finished_at='2026-03-30T11:03:00Z',
        )
    )

    latest_attempt = attempt_store.get_latest('att-2')
    assert latest_attempt is not None
    assert latest_attempt.attempt_state is AttemptState.COMPLETED
    assert [attempt.attempt_id for attempt in attempt_store.list_message('msg-1')] == ['att-1', 'att-2']
    assert [attempt.attempt_id for attempt in attempt_store.list_agent('Agent1')] == ['att-1', 'att-2']

    latest_reply = reply_store.get_latest('rep-1')
    assert latest_reply is not None
    assert latest_reply.agent_name == 'agent1'
    assert [reply.reply_id for reply in reply_store.list_message('msg-1')] == ['rep-1']
