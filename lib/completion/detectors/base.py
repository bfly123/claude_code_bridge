from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from completion.models import (
    CompletionConfidence,
    CompletionCursor,
    CompletionDecision,
    CompletionItem,
    CompletionItemKind,
    CompletionRequestContext,
    CompletionState,
    CompletionStatus,
    CompletionValidationError,
    first_non_empty,
    fingerprint_text,
)


class CompletionDetector(Protocol):
    def bind(self, request_ctx: CompletionRequestContext, baseline: CompletionCursor) -> None: ...

    def ingest(self, item: CompletionItem) -> None: ...

    def decision(self) -> CompletionDecision: ...

    def state(self) -> CompletionState: ...


class TickableCompletionDetector(Protocol):
    def tick(self, now: str, cursor: CompletionCursor | None = None) -> None: ...

    def finalize_timeout(self, now: str, cursor: CompletionCursor | None = None) -> None: ...


class BaseCompletionDetector:
    def __init__(self) -> None:
        self._request_ctx: CompletionRequestContext | None = None
        self._state = CompletionState()
        self._decision = CompletionDecision.pending()

    def bind(self, request_ctx: CompletionRequestContext, baseline: CompletionCursor) -> None:
        self._request_ctx = request_ctx
        self._state = CompletionState(latest_cursor=baseline)
        self._decision = CompletionDecision.pending(cursor=baseline)

    def decision(self) -> CompletionDecision:
        return self._decision

    def state(self) -> CompletionState:
        return replace(self._state)

    def tick(self, now: str, cursor: CompletionCursor | None = None) -> None:
        self._sync_cursor(cursor)

    def finalize_timeout(self, now: str, cursor: CompletionCursor | None = None) -> None:
        if self._decision.terminal:
            return
        self._sync_cursor(cursor)
        self._set_terminal(
            status=CompletionStatus.INCOMPLETE,
            reason='timeout',
            confidence=CompletionConfidence.DEGRADED,
            finished_at=now,
        )

    def _require_bound(self) -> CompletionRequestContext:
        if self._request_ctx is None:
            raise CompletionValidationError('detector must be bound before use')
        return self._request_ctx

    def _sync_cursor(self, cursor: CompletionCursor | None) -> None:
        if cursor is not None:
            self._state.latest_cursor = cursor

    def _consume_common_item(self, item: CompletionItem) -> None:
        self._sync_cursor(item.cursor)
        if item.kind is CompletionItemKind.ANCHOR_SEEN:
            self._state.anchor_seen = True
        elif item.kind is CompletionItemKind.TOOL_CALL:
            self._state.tool_active = True
        elif item.kind is CompletionItemKind.TOOL_RESULT:
            self._state.tool_active = False
        elif item.kind is CompletionItemKind.SESSION_ROTATE:
            self._state.anchor_seen = False
            self._state.reply_started = False
            self._state.reply_stable = False
            self._state.last_reply_hash = None
            self._state.last_reply_at = None
            self._state.stable_since = None
        if first_non_empty(item.payload, 'subagent_id', 'subagent_name'):
            self._state.subagent_activity_seen = True
        provider_turn_ref = first_non_empty(
            item.payload,
            'turn_id',
            'provider_turn_ref',
            'message_id',
            'provider_session_id',
            'session_id',
        )
        if provider_turn_ref:
            self._state.provider_turn_ref = provider_turn_ref

    def _record_reply(self, item: CompletionItem, text: str, *, stable: bool = False, fingerprint: str | None = None) -> None:
        message = (text or '').strip()
        if not message:
            return
        self._state.reply_started = True
        self._state.last_reply_hash = fingerprint or fingerprint_text(message)
        self._state.last_reply_at = item.timestamp
        if stable:
            self._state.reply_stable = True
        else:
            self._state.reply_stable = False

    @staticmethod
    def _terminal_diagnostics_from_item(item: CompletionItem) -> dict:
        payload = dict(item.payload or {})
        for key in ('reply', 'content', 'final_answer', 'result_text', 'last_agent_message'):
            payload.pop(key, None)
        return payload

    def _set_terminal(
        self,
        *,
        status: CompletionStatus,
        reason: str,
        confidence: CompletionConfidence,
        finished_at: str,
        reply: str = '',
        diagnostics: dict | None = None,
    ) -> None:
        self._state.terminal = True
        self._decision = CompletionDecision(
            terminal=True,
            status=status,
            reason=reason,
            confidence=confidence,
            reply=reply,
            anchor_seen=self._state.anchor_seen,
            reply_started=self._state.reply_started,
            reply_stable=self._state.reply_stable,
            provider_turn_ref=self._state.provider_turn_ref,
            source_cursor=self._state.latest_cursor,
            finished_at=finished_at,
            diagnostics=diagnostics or {},
        )

    def _set_pending(self) -> None:
        self._decision = CompletionDecision(
            terminal=False,
            status=CompletionStatus.INCOMPLETE,
            reason=None,
            confidence=None,
            reply='',
            anchor_seen=self._state.anchor_seen,
            reply_started=self._state.reply_started,
            reply_stable=self._state.reply_stable,
            provider_turn_ref=self._state.provider_turn_ref,
            source_cursor=self._state.latest_cursor,
            finished_at=None,
            diagnostics={},
        )

    def _terminal_status_from_abort(self, item: CompletionItem) -> CompletionStatus:
        raw_status = str(item.payload.get('status') or '').strip().lower()
        if raw_status in {'completed', 'cancelled', 'failed', 'incomplete'}:
            return CompletionStatus(raw_status)
        reason = str(item.payload.get('reason') or '').strip().lower()
        if 'cancel' in reason or 'abort' in reason:
            return CompletionStatus.CANCELLED
        return CompletionStatus.FAILED
