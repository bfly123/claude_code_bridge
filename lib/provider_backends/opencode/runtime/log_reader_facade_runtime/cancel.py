from __future__ import annotations

from opencode_runtime.replies import extract_req_id_from_text as _extract_req_id_from_text
from opencode_runtime.replies import is_aborted_error as _is_aborted_error

from ..cancel_tracking import detect_cancel_event_in_logs as _detect_cancel_event_in_logs
from ..cancel_tracking import detect_cancelled_since as _detect_cancelled_since
from ..cancel_tracking import open_cancel_log_cursor as _open_cancel_log_cursor
from .config import REQ_ID_RE


class OpenCodeCancelMixin:
    @staticmethod
    def _is_aborted_error(error_obj: object) -> bool:
        return _is_aborted_error(error_obj)

    @staticmethod
    def _extract_req_id_from_text(text: str) -> str | None:
        return _extract_req_id_from_text(text, REQ_ID_RE)

    def detect_cancelled_since(self, state: dict[str, object], *, req_id: str) -> tuple[bool, dict[str, object]]:
        return _detect_cancelled_since(self, state, req_id=req_id)

    def open_cancel_log_cursor(self) -> dict[str, object]:
        return _open_cancel_log_cursor()

    def detect_cancel_event_in_logs(
        self,
        cursor: dict[str, object],
        *,
        session_id: str,
        since_epoch_s: float,
    ) -> tuple[bool, dict[str, object]]:
        return _detect_cancel_event_in_logs(cursor, session_id=session_id, since_epoch_s=since_epoch_s)


__all__ = ['OpenCodeCancelMixin']
