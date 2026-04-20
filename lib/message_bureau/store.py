from __future__ import annotations

from agents.models import normalize_agent_name
from storage.jsonl_store import JsonlStore
from storage.paths import PathLayout

from .models import AttemptRecord, MessageRecord, ReplyRecord


class MessageStore:
    def __init__(self, layout: PathLayout, store: JsonlStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonlStore()

    def append(self, record: MessageRecord) -> None:
        self._store.append(self._layout.ccbd_messages_path, record, serializer=lambda value: value.to_record())

    def list_all(self) -> list[MessageRecord]:
        return self._store.read_all(self._layout.ccbd_messages_path, loader=MessageRecord.from_record)

    def get_latest(self, message_id: str) -> MessageRecord | None:
        for record in reversed(self.list_all()):
            if record.message_id == message_id:
                return record
        return None

    def list_submission(self, submission_id: str) -> list[MessageRecord]:
        return [record for record in self.list_all() if record.submission_id == submission_id]


class AttemptStore:
    def __init__(self, layout: PathLayout, store: JsonlStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonlStore()

    def append(self, record: AttemptRecord) -> None:
        self._store.append(self._layout.ccbd_attempts_path, record, serializer=lambda value: value.to_record())

    def list_all(self) -> list[AttemptRecord]:
        return self._store.read_all(self._layout.ccbd_attempts_path, loader=AttemptRecord.from_record)

    def get_latest(self, attempt_id: str) -> AttemptRecord | None:
        for record in reversed(self.list_all()):
            if record.attempt_id == attempt_id:
                return record
        return None

    def get_latest_by_job_id(self, job_id: str) -> AttemptRecord | None:
        for record in reversed(self.list_all()):
            if record.job_id == job_id:
                return record
        return None

    def list_message(self, message_id: str) -> list[AttemptRecord]:
        return [record for record in self.list_all() if record.message_id == message_id]

    def list_agent(self, agent_name: str) -> list[AttemptRecord]:
        normalized = normalize_agent_name(agent_name)
        return [record for record in self.list_all() if record.agent_name == normalized]


class ReplyStore:
    def __init__(self, layout: PathLayout, store: JsonlStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonlStore()

    def append(self, record: ReplyRecord) -> None:
        self._store.append(self._layout.ccbd_replies_path, record, serializer=lambda value: value.to_record())

    def list_all(self) -> list[ReplyRecord]:
        return self._store.read_all(self._layout.ccbd_replies_path, loader=ReplyRecord.from_record)

    def get_latest(self, reply_id: str) -> ReplyRecord | None:
        for record in reversed(self.list_all()):
            if record.reply_id == reply_id:
                return record
        return None

    def list_message(self, message_id: str) -> list[ReplyRecord]:
        return [record for record in self.list_all() if record.message_id == message_id]


__all__ = ['AttemptStore', 'MessageStore', 'ReplyStore']
