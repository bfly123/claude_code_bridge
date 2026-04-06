from __future__ import annotations

from pathlib import Path
from typing import Any

from opencode_runtime.storage import OpenCodeStorageAccessor

from ..reader_support import build_work_dir_candidates as _build_work_dir_candidates


class OpenCodeStorageMixin:
    def _session_dir(self) -> Path:
        return self._storage.session_dir(self.project_id)

    def _message_dir(self, session_id: str) -> Path:
        return self._storage.message_dir(session_id)

    def _part_dir(self, message_id: str) -> Path:
        return self._storage.part_dir(message_id)

    def _work_dir_candidates(self) -> list[str]:
        return _build_work_dir_candidates(self.work_dir)

    def _load_json(self, path: Path) -> dict:
        return self._storage.load_json(path)

    def _load_json_blob(self, raw: Any) -> dict:
        return self._storage.load_json_blob(raw)

    def _opencode_db_candidates(self) -> list[Path]:
        return self._storage.opencode_db_candidates()

    def _resolve_opencode_db_path(self) -> Path | None:
        return self._storage.resolve_opencode_db_path()

    def _fetch_opencode_db_rows(self, query: str, params: tuple[object, ...]) -> list:
        return self._storage.fetch_opencode_db_rows(query, params)

    @staticmethod
    def _message_sort_key(m: dict) -> tuple[int, float, str]:
        return OpenCodeStorageAccessor.message_sort_key(m)

    @staticmethod
    def _part_sort_key(p: dict) -> tuple[int, float, str]:
        return OpenCodeStorageAccessor.part_sort_key(p)


__all__ = ['OpenCodeStorageMixin']
