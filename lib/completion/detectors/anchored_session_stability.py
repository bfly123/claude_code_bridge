from __future__ import annotations

from completion.detectors.base import BaseCompletionDetector
from completion.models import (
    CompletionConfidence,
    CompletionCursor,
    CompletionItem,
    CompletionItemKind,
    CompletionStatus,
    first_non_empty,
    fingerprint_text,
    seconds_between,
)


class AnchoredSessionStabilityDetector(BaseCompletionDetector):
    def __init__(self, *, settle_window_s: float = 2.0) -> None:
        super().__init__()
        self._settle_window_s = settle_window_s

    def ingest(self, item: CompletionItem) -> None:
        self._require_bound()
        self._consume_common_item(item)

        if item.kind is CompletionItemKind.CANCEL_INFO:
            self._set_terminal(
                status=CompletionStatus.CANCELLED,
                reason=first_non_empty(item.payload, 'reason') or 'cancel_info',
                confidence=CompletionConfidence.OBSERVED,
                finished_at=item.timestamp,
            )
            return

        if item.kind in {CompletionItemKind.SESSION_SNAPSHOT, CompletionItemKind.SESSION_MUTATION}:
            raw_tool_calls = item.payload.get('tool_call_count')
            if raw_tool_calls is not None:
                try:
                    self._state.tool_active = int(raw_tool_calls) > 0
                except Exception:
                    self._state.tool_active = bool(raw_tool_calls)
            reply = first_non_empty(item.payload, 'reply', 'content', 'text')
            if reply:
                fingerprint = fingerprint_text(
                    first_non_empty(item.payload, 'message_id') or '',
                    reply,
                    item.payload.get('message_count'),
                    item.payload.get('last_updated'),
                )
                if fingerprint != self._state.last_reply_hash:
                    self._record_reply(item, reply, fingerprint=fingerprint)
                    self._state.stable_since = item.timestamp
                self._set_pending()
                return

        if item.kind is CompletionItemKind.ERROR:
            self._set_terminal(
                status=CompletionStatus.FAILED,
                reason=first_non_empty(item.payload, 'reason', 'error') or 'session_corrupt',
                confidence=CompletionConfidence.OBSERVED,
                finished_at=item.timestamp,
            )
            return

        if item.kind is CompletionItemKind.PANE_DEAD:
            self._set_terminal(
                status=CompletionStatus.FAILED,
                reason=first_non_empty(item.payload, 'reason') or 'pane_dead',
                confidence=CompletionConfidence.DEGRADED,
                finished_at=item.timestamp,
            )
            return

        self._set_pending()

    def tick(self, now: str, cursor: CompletionCursor | None = None) -> None:
        super().tick(now, cursor)
        if self._decision.terminal:
            return
        if not self._state.reply_started or self._state.stable_since is None:
            return
        if self._state.tool_active:
            self._set_pending()
            return
        if seconds_between(self._state.stable_since, now) >= self._settle_window_s:
            self._state.reply_stable = True
            self._set_terminal(
                status=CompletionStatus.COMPLETED,
                reason='session_reply_stable',
                confidence=CompletionConfidence.OBSERVED,
                finished_at=now,
            )
        else:
            self._set_pending()

    def finalize_timeout(self, now: str, cursor: CompletionCursor | None = None) -> None:
        self._require_bound()
        if self._decision.terminal:
            return
        self._sync_cursor(cursor)
        super().finalize_timeout(now, cursor)
