from __future__ import annotations

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
from storage.json_store import JsonStore
from storage.paths import PathLayout

SCHEMA_VERSION = 2


class CompletionSnapshotStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self, job_id: str) -> CompletionSnapshot | None:
        path = self._layout.snapshot_path(job_id)
        if not path.exists():
            return None
        return self._store.load(path, loader=_completion_snapshot_from_record)

    def save(self, snapshot: CompletionSnapshot) -> None:
        self._store.save(self._layout.snapshot_path(snapshot.job_id), snapshot, serializer=lambda value: value.to_record())


def _validate_record(record: dict, expected_type: str) -> None:
    if record.get('schema_version') != SCHEMA_VERSION:
        raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
    if record.get('record_type') != expected_type:
        raise ValueError(f'record_type must be {expected_type!r}')


def _cursor_from_record(record: dict | None) -> CompletionCursor | None:
    if record is None:
        return None
    _validate_record(record, 'completion_cursor')
    return CompletionCursor(
        source_kind=CompletionSourceKind(record['source_kind']),
        opaque_cursor=record.get('opaque_cursor'),
        session_path=record.get('session_path'),
        offset=record.get('offset'),
        line_no=record.get('line_no'),
        event_seq=record.get('event_seq'),
        updated_at=record.get('updated_at'),
    )


def _state_from_record(record: dict) -> CompletionState:
    _validate_record(record, 'completion_state')
    return CompletionState(
        anchor_seen=bool(record.get('anchor_seen', False)),
        reply_started=bool(record.get('reply_started', False)),
        reply_stable=bool(record.get('reply_stable', False)),
        tool_active=bool(record.get('tool_active', False)),
        subagent_activity_seen=bool(record.get('subagent_activity_seen', False)),
        last_reply_hash=record.get('last_reply_hash'),
        last_reply_at=record.get('last_reply_at'),
        stable_since=record.get('stable_since'),
        provider_turn_ref=record.get('provider_turn_ref'),
        latest_cursor=_cursor_from_record(record.get('latest_cursor')),
        terminal=bool(record.get('terminal', False)),
    )


def _decision_from_record(record: dict) -> CompletionDecision:
    _validate_record(record, 'completion_decision')
    return CompletionDecision(
        terminal=bool(record['terminal']),
        status=CompletionStatus(record['status']),
        reason=record.get('reason'),
        confidence=CompletionConfidence(record['confidence']) if record.get('confidence') is not None else None,
        reply=record.get('reply', ''),
        anchor_seen=bool(record.get('anchor_seen', False)),
        reply_started=bool(record.get('reply_started', False)),
        reply_stable=bool(record.get('reply_stable', False)),
        provider_turn_ref=record.get('provider_turn_ref'),
        source_cursor=_cursor_from_record(record.get('source_cursor')),
        finished_at=record.get('finished_at'),
        diagnostics=dict(record.get('diagnostics', {})),
    )


def _completion_snapshot_from_record(record: dict) -> CompletionSnapshot:
    _validate_record(record, 'completion_snapshot')
    return CompletionSnapshot(
        job_id=record['job_id'],
        agent_name=record['agent_name'],
        profile_family=CompletionFamily(record['profile_family']),
        state=_state_from_record(record['state']),
        latest_decision=_decision_from_record(record['latest_decision']),
        latest_reply_preview=record.get('latest_reply_preview', ''),
        updated_at=record['updated_at'],
    )
