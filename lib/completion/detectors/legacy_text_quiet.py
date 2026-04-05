from __future__ import annotations

from completion.detectors.base import BaseCompletionDetector
from completion.models import CompletionConfidence, CompletionCursor, CompletionItem, CompletionItemKind, CompletionStatus, first_non_empty


class LegacyTextQuietDetector(BaseCompletionDetector):
    def ingest(self, item: CompletionItem) -> None:
        self._require_bound()
        self._consume_common_item(item)

        if item.kind in {CompletionItemKind.ASSISTANT_CHUNK, CompletionItemKind.ASSISTANT_FINAL, CompletionItemKind.RESULT}:
            reply = first_non_empty(item.payload, 'reply', 'result_text', 'final_answer', 'text')
            if reply:
                self._record_reply(item, reply)
            if item.payload.get('done_marker') or item.payload.get('ccb_done'):
                self._set_terminal(
                    status=CompletionStatus.COMPLETED,
                    reason='legacy_done_marker',
                    confidence=CompletionConfidence.DEGRADED,
                    finished_at=item.timestamp,
                    reply=reply or '',
                )
                return
            self._set_pending()
            return

        if item.kind is CompletionItemKind.CANCEL_INFO:
            self._set_terminal(
                status=CompletionStatus.CANCELLED,
                reason=first_non_empty(item.payload, 'reason') or 'cancel_info',
                confidence=CompletionConfidence.DEGRADED,
                finished_at=item.timestamp,
            )
            return

        if item.kind is CompletionItemKind.ERROR:
            self._set_terminal(
                status=CompletionStatus.FAILED,
                reason=first_non_empty(item.payload, 'reason', 'error') or 'transport_error',
                confidence=CompletionConfidence.DEGRADED,
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

    def finalize_timeout(self, now: str, cursor: CompletionCursor | None = None) -> None:
        self._require_bound()
        if self._decision.terminal:
            return
        self._sync_cursor(cursor)
        if self._state.reply_started:
            self._set_terminal(
                status=CompletionStatus.COMPLETED,
                reason='legacy_quiet',
                confidence=CompletionConfidence.DEGRADED,
                finished_at=now,
            )
            return
        super().finalize_timeout(now, cursor)
