from __future__ import annotations

from storage.jsonl_store import JsonlStore
from storage.paths import PathLayout

from .health import ProviderHealthSnapshot


class ProviderHealthSnapshotStore:
    def __init__(self, layout: PathLayout, store: JsonlStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonlStore()

    def append(self, snapshot: ProviderHealthSnapshot) -> None:
        self._store.append(
            self._layout.provider_health_path(snapshot.job_id),
            snapshot,
            serializer=lambda value: value.to_record(),
        )

    def list_job(self, job_id: str) -> list[ProviderHealthSnapshot]:
        return self._store.read_all(
            self._layout.provider_health_path(job_id),
            loader=ProviderHealthSnapshot.from_record,
        )

    def latest(self, job_id: str) -> ProviderHealthSnapshot | None:
        records = self.list_job(job_id)
        if not records:
            return None
        return records[-1]

    def list_all(self) -> list[ProviderHealthSnapshot]:
        directory = self._layout.ccbd_provider_health_dir
        if not directory.exists():
            return []
        snapshots: list[ProviderHealthSnapshot] = []
        for path in sorted(directory.glob('*.jsonl')):
            try:
                snapshots.extend(self._store.read_all(path, loader=ProviderHealthSnapshot.from_record))
            except Exception:
                continue
        return snapshots


__all__ = ['ProviderHealthSnapshotStore']
