from __future__ import annotations

from completion.detectors.base import BaseCompletionDetector
from completion.models import CompletionConfidence, CompletionItem, CompletionItemKind, CompletionStatus, first_non_empty


class StructuredResultDetector(BaseCompletionDetector):
    def ingest(self, item: CompletionItem) -> None:
        self._require_bound()
        self._consume_common_item(item)

        if item.kind in {CompletionItemKind.ASSISTANT_CHUNK, CompletionItemKind.ASSISTANT_FINAL}:
            self._record_stream_reply(item)
            self._set_pending()
            return

        if item.kind is CompletionItemKind.RESULT:
            self._complete_from_result(item)
            return

        if item.kind is CompletionItemKind.CANCEL_INFO:
            self._terminal_from_item(
                item,
                status=CompletionStatus.CANCELLED,
                reason=first_non_empty(item.payload, 'reason') or 'cancel_info',
                confidence=CompletionConfidence.EXACT,
            )
            return

        if item.kind is CompletionItemKind.TURN_ABORTED:
            self._terminal_from_item(
                item,
                status=self._terminal_status_from_abort(item),
                reason=first_non_empty(item.payload, 'reason') or 'turn_aborted',
                confidence=CompletionConfidence.EXACT,
            )
            return

        if item.kind is CompletionItemKind.ERROR:
            self._terminal_from_item(
                item,
                status=CompletionStatus.FAILED,
                reason=first_non_empty(item.payload, 'reason', 'error') or 'transport_error',
                confidence=CompletionConfidence.EXACT,
            )
            return

        if item.kind is CompletionItemKind.PANE_DEAD:
            self._terminal_from_item(
                item,
                status=CompletionStatus.FAILED,
                reason=first_non_empty(item.payload, 'reason') or 'pane_dead',
                confidence=CompletionConfidence.DEGRADED,
            )
            return

        self._set_pending()

    def _record_stream_reply(self, item: CompletionItem) -> None:
        text = first_non_empty(item.payload, 'reply', 'final_answer', 'text')
        if text:
            self._record_reply(item, text)

    def _complete_from_result(self, item: CompletionItem) -> None:
        reply = first_non_empty(item.payload, 'reply', 'result_text', 'final_answer', 'text') or ''
        if reply:
            self._record_reply(item, reply, stable=True)
        self._set_terminal(
            status=CompletionStatus.COMPLETED,
            reason=first_non_empty(item.payload, 'reason', 'completion_reason') or 'stream_result',
            confidence=CompletionConfidence.EXACT,
            finished_at=item.timestamp,
            reply=reply,
        )

    def _terminal_from_item(
        self,
        item: CompletionItem,
        *,
        status: CompletionStatus,
        reason: str,
        confidence: CompletionConfidence,
    ) -> None:
        self._set_terminal(
            status=status,
            reason=reason,
            confidence=confidence,
            finished_at=item.timestamp,
            diagnostics=self._terminal_diagnostics_from_item(item),
        )
