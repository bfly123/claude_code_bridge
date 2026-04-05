from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from ccbd.api_models import JobRecord
from ccbd.system import parse_utc_timestamp
from completion.models import (
    CompletionCursor,
    CompletionItem,
    CompletionItemKind,
    CompletionSourceKind,
)

from .base import ProviderPollResult, ProviderSubmission
from .fake_runtime import (
    DEFAULT_LATENCY_SECONDS,
    FakeDirective,
    FakeScriptEvent,
    TERMINAL_KINDS,
    build_terminal_decision,
    default_script,
    first_text,
    materialize_payload,
    normalize_script_event,
    parse_directive,
)


class FakeProviderAdapter:
    def __init__(
        self,
        *,
        provider: str = 'fake',
        source_kind: CompletionSourceKind = CompletionSourceKind.STRUCTURED_RESULT_STREAM,
        script_mode: str = 'structured_result',
        latency_seconds: float = DEFAULT_LATENCY_SECONDS,
    ) -> None:
        self.provider = provider
        self._source_kind = source_kind
        self._script_mode = script_mode
        self._latency_seconds = latency_seconds

    def start(self, job: JobRecord, *, context, now: str) -> ProviderSubmission:
        del context
        directive = parse_directive(job.request.task_id, default_latency_seconds=self._latency_seconds)
        events = tuple(normalize_script_event(raw) for raw in (directive.script or default_script(directive, mode=self._script_mode)))
        max_delay_ms = max((event.at_ms for event in events), default=0)
        ready_at = parse_utc_timestamp(now) + timedelta(milliseconds=max_delay_ms)
        reply = f'FAKE[{job.agent_name}] {job.request.body}'
        return ProviderSubmission(
            job_id=job.job_id,
            agent_name=job.agent_name,
            provider=self.provider,
            accepted_at=now,
            ready_at=ready_at.isoformat().replace('+00:00', 'Z'),
            source_kind=self._source_kind,
            reply=reply,
            status=directive.status,
            reason=directive.reason,
            confidence=directive.confidence,
            diagnostics={'provider': self.provider, 'task_id': job.request.task_id},
            runtime_state={
                'events': [
                    {
                        'at_ms': event.at_ms,
                        'kind': event.kind.value if event.kind is not None else None,
                        'payload': dict(event.payload),
                    }
                    for event in events
                ],
                'next_index': 0,
                'next_seq': 1,
                'reply_buffer': '',
            },
        )

    def poll(self, submission: ProviderSubmission, *, now: str) -> ProviderPollResult | None:
        state = dict(submission.runtime_state)
        events = list(state.get('events', []))
        next_index = int(state.get('next_index', 0))
        next_seq = int(state.get('next_seq', 1))
        reply_buffer = str(state.get('reply_buffer', ''))
        elapsed_ms = max(
            0,
            int((parse_utc_timestamp(now) - parse_utc_timestamp(submission.accepted_at)).total_seconds() * 1000),
        )

        emitted: list[CompletionItem] = []
        decision: CompletionDecision | None = None
        accepted_at = parse_utc_timestamp(submission.accepted_at)

        while next_index < len(events):
            raw_event = events[next_index]
            at_ms = int(raw_event['at_ms'])
            if at_ms > elapsed_ms:
                break

            kind_name = raw_event.get('kind')
            payload = dict(raw_event.get('payload') or {})
            next_index += 1
            if kind_name is None:
                continue

            kind = CompletionItemKind(str(kind_name))
            timestamp = (accepted_at + timedelta(milliseconds=at_ms)).isoformat().replace('+00:00', 'Z')
            payload, reply_buffer = materialize_payload(
                kind,
                payload,
                reply_buffer=reply_buffer,
                default_reply=submission.reply,
                turn_ref=submission.job_id,
                terminal_reason=submission.reason,
            )
            cursor = CompletionCursor(
                source_kind=submission.source_kind,
                event_seq=next_seq,
                updated_at=timestamp,
            )
            item = CompletionItem(
                kind=kind,
                timestamp=timestamp,
                cursor=cursor,
                provider=submission.provider,
                agent_name=submission.agent_name,
                req_id=submission.job_id,
                payload=payload,
            )
            emitted.append(item)
            next_seq += 1

            if kind in TERMINAL_KINDS:
                decision = build_terminal_decision(
                    submission,
                    payload=payload,
                    cursor=cursor,
                    finished_at=timestamp,
                    reply=reply_buffer or submission.reply,
                )
                break

        if not emitted and decision is None:
            return None

        updated = replace(
            submission,
            runtime_state={
                **state,
                'next_index': next_index,
                'next_seq': next_seq,
                'reply_buffer': reply_buffer,
            },
        )
        return ProviderPollResult(submission=updated, items=tuple(emitted), decision=decision)

    def export_runtime_state(self, submission: ProviderSubmission) -> dict[str, object]:
        return dict(submission.runtime_state)

    def resume(self, job: JobRecord, submission: ProviderSubmission, *, context, persisted_state, now: str) -> ProviderSubmission | None:
        del context, persisted_state, now
        if submission.job_id != job.job_id or submission.provider != job.provider:
            return None
        return submission


_build_terminal_decision = build_terminal_decision
_default_script = default_script
_first_text = first_text
_materialize_payload = materialize_payload
_normalize_script_event = normalize_script_event
_parse_directive = parse_directive


__all__ = [
    'FakeDirective',
    'FakeProviderAdapter',
    'FakeScriptEvent',
]
