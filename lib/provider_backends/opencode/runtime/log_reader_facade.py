from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from provider_core.protocol import ANY_REQ_ID_PATTERN, REQ_ID_BOUNDARY_PATTERN, REQ_ID_PREFIX
from opencode_runtime.paths import OPENCODE_STORAGE_ROOT
from opencode_runtime.replies import extract_req_id_from_text as _extract_req_id_from_text
from opencode_runtime.replies import extract_text as _extract_text
from opencode_runtime.replies import is_aborted_error as _is_aborted_error
from opencode_runtime.storage import OpenCodeStorageAccessor

from . import (
    allow_any_session as _allow_any_session,
    allow_git_root_fallback as _allow_git_root_fallback,
    allow_parent_workdir_match as _allow_parent_workdir_match,
    allow_session_rollover as _allow_session_rollover,
    build_work_dir_candidates as _build_work_dir_candidates,
    capture_state as _capture_state,
    conversations_for_session as _conversations_for_session_runtime,
    detect_cancel_event_in_logs as _detect_cancel_event_in_logs,
    detect_cancelled_since as _detect_cancelled_since,
    detect_project_id_for_workdir as _detect_project_id_for_workdir,
    fallback_project_id as _fallback_project_id,
    get_latest_session as _get_latest_session,
    get_latest_session_from_db as _get_latest_session_from_db,
    get_latest_session_from_files as _get_latest_session_from_files,
    latest_conversations as _latest_conversations_runtime,
    latest_message as _latest_message_runtime,
    open_cancel_log_cursor as _open_cancel_log_cursor,
    read_messages as _read_messages_runtime,
    read_parts as _read_parts_runtime,
    read_since as _read_since_runtime,
)

_REQ_ID_RE = re.compile(rf"{re.escape(REQ_ID_PREFIX)}\s*({ANY_REQ_ID_PATTERN}){REQ_ID_BOUNDARY_PATTERN}", re.IGNORECASE)


class OpenCodeLogReader:
    """
    Reads OpenCode session/message/part data from storage JSON files or SQLite.

    Observed storage layout:
      storage/session/<projectID>/ses_*.json
      storage/message/<sessionID>/msg_*.json
      storage/part/<messageID>/prt_*.json
      ../opencode.db (message/part tables)
    """

    def __init__(
        self,
        root: Path = OPENCODE_STORAGE_ROOT,
        work_dir: Path | None = None,
        project_id: str = "global",
        *,
        session_id_filter: str | None = None,
    ):
        self.root = Path(root).expanduser()
        self._storage = OpenCodeStorageAccessor(self.root)
        self.work_dir = work_dir or Path.cwd()
        env_project_id = (os.environ.get("OPENCODE_PROJECT_ID") or "").strip()
        explicit_project_id = bool(env_project_id) or ((project_id or "").strip() not in ("", "global"))
        self._allow_parent_match = _allow_parent_workdir_match()
        self._allow_any_session = _allow_any_session()
        self._allow_session_rollover = _allow_session_rollover()
        allow_git_root_fallback = _allow_git_root_fallback()
        self.project_id = (env_project_id or project_id or "global").strip() or "global"
        self._session_id_filter = (session_id_filter or "").strip() or None
        if not explicit_project_id:
            detected = self._detect_project_id_for_workdir()
            if detected:
                self.project_id = detected
            elif allow_git_root_fallback:
                self.project_id = _fallback_project_id(self.work_dir)

        try:
            poll = float(os.environ.get("OPENCODE_POLL_INTERVAL", "0.05"))
        except Exception:
            poll = 0.05
        self._poll_interval = min(0.5, max(0.02, poll))

        try:
            force = float(os.environ.get("OPENCODE_FORCE_READ_INTERVAL", "1.0"))
        except Exception:
            force = 1.0
        self._force_read_interval = min(5.0, max(0.2, force))

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

    def _detect_project_id_for_workdir(self) -> str | None:
        return _detect_project_id_for_workdir(
            storage_root=self.root,
            work_dir=self.work_dir,
            load_json_fn=self._load_json,
            allow_parent_match=self._allow_parent_match,
        )

    def _get_latest_session(self) -> dict | None:
        return _get_latest_session(self)

    def _get_latest_session_from_db(self) -> dict | None:
        return _get_latest_session_from_db(self)

    def _get_latest_session_from_files(self) -> dict | None:
        return _get_latest_session_from_files(self)

    def _read_messages(self, session_id: str) -> list[dict]:
        return _read_messages_runtime(self, session_id)

    def _read_parts(self, message_id: str) -> list[dict]:
        return _read_parts_runtime(self, message_id)

    @staticmethod
    def _extract_text(parts: list[dict], allow_reasoning_fallback: bool = True) -> str:
        return _extract_text(parts, allow_reasoning_fallback=allow_reasoning_fallback)

    def capture_state(self) -> dict[str, Any]:
        return _capture_state(self)

    def _read_since(self, state: dict[str, Any], timeout: float, block: bool) -> tuple[str | None, dict[str, Any]]:
        return _read_since_runtime(self, state, timeout, block)

    def wait_for_message(self, state: dict[str, Any], timeout: float) -> tuple[str | None, dict[str, Any]]:
        return self._read_since(state, timeout, block=True)

    def try_get_message(self, state: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
        return self._read_since(state, timeout=0.0, block=False)

    def latest_message(self) -> str | None:
        return _latest_message_runtime(self)

    def conversations_for_session(self, session_id: str, n: int = 1) -> list[tuple[str, str]]:
        return _conversations_for_session_runtime(self, session_id, n=n)

    def latest_conversations(self, n: int = 1) -> list[tuple[str, str]]:
        return _latest_conversations_runtime(self, n=n)

    @staticmethod
    def _is_aborted_error(error_obj: object) -> bool:
        return _is_aborted_error(error_obj)

    @staticmethod
    def _extract_req_id_from_text(text: str) -> str | None:
        return _extract_req_id_from_text(text, _REQ_ID_RE)

    def detect_cancelled_since(self, state: dict[str, Any], *, req_id: str) -> tuple[bool, dict[str, Any]]:
        return _detect_cancelled_since(self, state, req_id=req_id)

    def open_cancel_log_cursor(self) -> dict[str, Any]:
        return _open_cancel_log_cursor()

    def detect_cancel_event_in_logs(
        self, cursor: dict[str, Any], *, session_id: str, since_epoch_s: float
    ) -> tuple[bool, dict[str, Any]]:
        return _detect_cancel_event_in_logs(cursor, session_id=session_id, since_epoch_s=since_epoch_s)


__all__ = ["OpenCodeLogReader"]
