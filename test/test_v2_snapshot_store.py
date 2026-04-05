from __future__ import annotations

from pathlib import Path

from completion.models import (
    CompletionConfidence,
    CompletionCursor,
    CompletionDecision,
    CompletionFamily,
    CompletionSnapshot,
    CompletionSourceKind,
    CompletionState,
    CompletionStatus,
)
from completion.snapshot_store import CompletionSnapshotStore
from storage.cursor_store import CursorStore
from storage.paths import PathLayout


def test_snapshot_store_roundtrip(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    cursor = CompletionCursor(source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM, event_seq=2)
    snapshot = CompletionSnapshot(
        job_id='job-1',
        agent_name='agent1',
        profile_family=CompletionFamily.PROTOCOL_TURN,
        state=CompletionState(anchor_seen=True, reply_started=True, latest_cursor=cursor),
        latest_decision=CompletionDecision(
            terminal=True,
            status=CompletionStatus.COMPLETED,
            reason='task_complete',
            confidence=CompletionConfidence.EXACT,
            reply='done',
            anchor_seen=True,
            reply_started=True,
            reply_stable=False,
            provider_turn_ref='turn-1',
            source_cursor=cursor,
            finished_at='2026-03-18T00:00:03Z',
            diagnostics={},
        ),
        latest_reply_preview='done',
        updated_at='2026-03-18T00:00:03Z',
    )

    store = CompletionSnapshotStore(layout)
    store.save(snapshot)
    loaded = store.load('job-1')
    assert loaded == snapshot


def test_cursor_store_roundtrip(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    cursor = CompletionCursor(
        source_kind=CompletionSourceKind.SESSION_SNAPSHOT,
        session_path='/tmp/session.json',
        event_seq=3,
        updated_at='2026-03-18T00:00:03Z',
    )

    store = CursorStore(layout)
    store.save('job-1', cursor)
    assert store.load('job-1') == cursor
