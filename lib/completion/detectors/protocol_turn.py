from __future__ import annotations

from completion.detectors.base import BaseCompletionDetector
from completion.models import CompletionConfidence, CompletionItem, CompletionItemKind, CompletionStatus, first_non_empty


class ProtocolTurnDetector(BaseCompletionDetector):
    def ingest(self, item: CompletionItem) -> None:
        self._require_bound()
        self._consume_common_item(item)

        if item.kind in {CompletionItemKind.ASSISTANT_CHUNK, CompletionItemKind.ASSISTANT_FINAL, CompletionItemKind.RESULT}:
            text = first_non_empty(item.payload, 'last_agent_message', 'final_answer', 'reply', 'result_text', 'text')
            if text:
                self._record_reply(item, text)
            self._set_pending()
            return

        if item.kind is CompletionItemKind.TURN_BOUNDARY:
            reply = first_non_empty(item.payload, 'last_agent_message', 'final_answer', 'reply', 'text') or ''
            if reply:
                self._record_reply(item, reply, stable=True)
            self._set_terminal(
                status=CompletionStatus.COMPLETED,
                reason=first_non_empty(item.payload, 'reason', 'completion_reason') or 'task_complete',
                confidence=CompletionConfidence.EXACT,
                finished_at=item.timestamp,
                reply=reply,
            )
            return

        if item.kind is CompletionItemKind.TURN_ABORTED:
            reply = first_non_empty(item.payload, 'last_agent_message', 'reply', 'text') or ''
            if reply:
                self._record_reply(item, reply, stable=True)
            self._set_terminal(
                status=self._terminal_status_from_abort(item),
                reason=first_non_empty(item.payload, 'reason') or 'turn_aborted',
                confidence=CompletionConfidence.EXACT,
                finished_at=item.timestamp,
                reply=reply,
                diagnostics=self._terminal_diagnostics_from_item(item),
            )
            return

        if item.kind is CompletionItemKind.ERROR:
            self._set_terminal(
                status=CompletionStatus.FAILED,
                reason=first_non_empty(item.payload, 'reason', 'error') or 'transport_error',
                confidence=CompletionConfidence.DEGRADED,
                finished_at=item.timestamp,
                diagnostics=self._terminal_diagnostics_from_item(item),
            )
            return

        if item.kind is CompletionItemKind.PANE_DEAD:
            self._set_terminal(
                status=CompletionStatus.FAILED,
                reason=first_non_empty(item.payload, 'reason') or 'pane_dead',
                confidence=CompletionConfidence.DEGRADED,
                finished_at=item.timestamp,
                diagnostics=self._terminal_diagnostics_from_item(item),
            )
            return

        self._set_pending()
