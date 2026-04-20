from __future__ import annotations

from storage.json_store import JsonStore
from storage.jsonl_store import JsonlStore
from storage.paths import PathLayout

from .models import DeliveryLease, InboundEventRecord, MailboxRecord


class MailboxStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self, agent_name: str) -> MailboxRecord | None:
        path = self._layout.agent_mailbox_path(agent_name)
        if not path.exists():
            return None
        return self._store.load(path, loader=MailboxRecord.from_record)

    def save(self, record: MailboxRecord) -> None:
        self._store.save(
            self._layout.agent_mailbox_path(record.agent_name),
            record,
            serializer=lambda value: value.to_record(),
        )

    def list_all(self) -> list[MailboxRecord]:
        directory = self._layout.ccbd_mailboxes_dir
        if not directory.exists():
            return []
        records: list[MailboxRecord] = []
        for path in sorted(directory.glob('*/mailbox.json')):
            try:
                records.append(self._store.load(path, loader=MailboxRecord.from_record))
            except Exception:
                continue
        return records


class InboundEventStore:
    def __init__(self, layout: PathLayout, store: JsonlStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonlStore()

    def append(self, record: InboundEventRecord) -> None:
        self._store.append(
            self._layout.agent_inbox_path(record.agent_name),
            record,
            serializer=lambda value: value.to_record(),
        )

    def list_agent(self, agent_name: str) -> list[InboundEventRecord]:
        return self._store.read_all(
            self._layout.agent_inbox_path(agent_name),
            loader=InboundEventRecord.from_record,
        )

    def read_since(self, agent_name: str, start_line: int = 0) -> tuple[int, list[InboundEventRecord]]:
        line_no, rows = self._store.read_since(
            self._layout.agent_inbox_path(agent_name),
            start_line,
            loader=InboundEventRecord.from_record,
        )
        return line_no, list(rows)

    def get_latest(self, agent_name: str, inbound_event_id: str) -> InboundEventRecord | None:
        for record in reversed(self.list_agent(agent_name)):
            if record.inbound_event_id == inbound_event_id:
                return record
        return None

    def get_latest_for_attempt(self, agent_name: str, attempt_id: str) -> InboundEventRecord | None:
        for record in reversed(self.list_agent(agent_name)):
            if record.attempt_id == attempt_id:
                return record
        return None


class DeliveryLeaseStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self, agent_name: str) -> DeliveryLease | None:
        path = self._layout.mailbox_lease_path(agent_name)
        if not path.exists():
            return None
        return self._store.load(path, loader=DeliveryLease.from_record)

    def save(self, record: DeliveryLease) -> None:
        self._store.save(
            self._layout.mailbox_lease_path(record.agent_name),
            record,
            serializer=lambda value: value.to_record(),
        )

    def remove(self, agent_name: str) -> None:
        path = self._layout.mailbox_lease_path(agent_name)
        try:
            path.unlink()
        except FileNotFoundError:
            return

    def list_all(self) -> list[DeliveryLease]:
        directory = self._layout.ccbd_leases_dir
        if not directory.exists():
            return []
        leases: list[DeliveryLease] = []
        for path in sorted(directory.glob('*.json')):
            try:
                leases.append(self._store.load(path, loader=DeliveryLease.from_record))
            except Exception:
                continue
        return leases


__all__ = ['DeliveryLeaseStore', 'InboundEventStore', 'MailboxStore']
