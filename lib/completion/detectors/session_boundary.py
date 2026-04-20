from __future__ import annotations

from completion.detectors.base import BaseCompletionDetector
from completion.models import CompletionConfidence, CompletionItem, CompletionItemKind, CompletionStatus, first_non_empty


class SessionBoundaryDetector(BaseCompletionDetector):
    def ingest(self, item: CompletionItem) -> None:
        self._require_bound()
        self._consume_common_item(item)

        if item.kind in {CompletionItemKind.ASSISTANT_CHUNK, CompletionItemKind.ASSISTANT_FINAL}:
            text = first_non_empty(item.payload, 'text', 'reply', 'last_agent_message')
            if text:
                self._record_reply(item, text)
            self._set_pending()
            return

        if item.kind is CompletionItemKind.TURN_BOUNDARY:
            reply = first_non_empty(item.payload, 'last_agent_message', 'reply', 'text') or ''
            if reply:
                self._record_reply(item, reply, stable=True)
            self._set_terminal(
                status=CompletionStatus.COMPLETED,
                reason=first_non_empty(item.payload, 'reason', 'completion_reason') or 'turn_duration',
                confidence=CompletionConfidence.OBSERVED,
                finished_at=item.timestamp,
                reply=reply,
            )
            return

        if item.kind is CompletionItemKind.ERROR:
            self._set_terminal(
                status=CompletionStatus.FAILED,
                reason=first_non_empty(item.payload, 'reason', 'error') or 'api_error',
                confidence=CompletionConfidence.OBSERVED,
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
