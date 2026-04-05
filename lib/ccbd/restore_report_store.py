from __future__ import annotations

from ccbd.models import CcbdRestoreReport
from storage.json_store import JsonStore
from storage.paths import PathLayout


class CcbdRestoreReportStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self) -> CcbdRestoreReport | None:
        path = self._layout.ccbd_restore_report_path
        if not path.exists():
            return None
        return self._store.load(path, loader=CcbdRestoreReport.from_record)

    def save(self, report: CcbdRestoreReport) -> None:
        self._store.save(self._layout.ccbd_restore_report_path, report, serializer=lambda value: value.to_record())


__all__ = ['CcbdRestoreReportStore']
