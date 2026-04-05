from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import uuid4

from ccbd.api_models import JobRecord
from completion.models import (
    CompletionConfidence,
    CompletionCursor,
    CompletionDecision,
    CompletionItem,
    CompletionItemKind,
    CompletionSourceKind,
    CompletionStatus,
)
from storage.paths import PathLayout

from .models import FaultRule
from .store import FaultInjectionStore

_DEFAULT_ERROR_MESSAGE = 'fault injection drill'


@dataclass(frozen=True)
class ConsumedFault:
    rule_id: str
    agent_name: str
    task_id: str
    reason: str
    error_message: str
    remaining_count: int
    injected_at: str


class FaultInjectionService:
    def __init__(
        self,
        layout: PathLayout,
        *,
        clock,
        store: FaultInjectionStore | None = None,
    ) -> None:
        self._layout = layout
        self._clock = clock
        self._store = store or FaultInjectionStore(layout)

    def list_rules(self) -> tuple[FaultRule, ...]:
        return tuple(
            sorted(
                self._store.load_rules(),
                key=lambda item: (item.created_at, item.rule_id),
            )
        )

    def arm_rule(
        self,
        *,
        agent_name: str,
        task_id: str,
        reason: str,
        count: int,
        error_message: str | None = None,
    ) -> FaultRule:
        now = self._clock()
        rule = FaultRule(
            rule_id=self._new_id('flt'),
            agent_name=agent_name,
            task_id=task_id,
            reason=reason,
            remaining_count=count,
            error_message=str(error_message or _DEFAULT_ERROR_MESSAGE).strip(),
            created_at=now,
            updated_at=now,
        )
        rules = list(self._store.load_rules())
        rules.append(rule)
        self._store.save_rules(tuple(rules))
        return rule

    def clear_rule(self, target: str) -> tuple[FaultRule, ...]:
        key = str(target or '').strip()
        if not key:
            raise ValueError('fault clear requires <rule_id|all>')
        rules = list(self._store.load_rules())
        if key == 'all':
            self._store.save_rules(())
            return tuple(rules)
        kept: list[FaultRule] = []
        cleared: list[FaultRule] = []
        for rule in rules:
            if rule.rule_id == key:
                cleared.append(rule)
            else:
                kept.append(rule)
        if not cleared:
            raise ValueError(f'fault rule not found: {key}')
        self._store.save_rules(tuple(kept))
        return tuple(cleared)

    def consume_for_job(self, job: JobRecord, *, now: str | None = None) -> ConsumedFault | None:
        task_id = str(job.request.task_id or '').strip()
        if not task_id:
            return None
        timestamp = str(now or self._clock())
        rules = list(self._store.load_rules())
        for index, rule in enumerate(rules):
            if rule.agent_name != job.agent_name:
                continue
            if rule.task_id != task_id:
                continue
            remaining_count = int(rule.remaining_count) - 1
            consumed = ConsumedFault(
                rule_id=rule.rule_id,
                agent_name=rule.agent_name,
                task_id=rule.task_id,
                reason=rule.reason,
                error_message=rule.error_message or _DEFAULT_ERROR_MESSAGE,
                remaining_count=max(remaining_count, 0),
                injected_at=timestamp,
            )
            if remaining_count > 0:
                rules[index] = replace(rule, remaining_count=remaining_count, updated_at=timestamp)
            else:
                del rules[index]
            self._store.save_rules(tuple(rules))
            return consumed
        return None

    @staticmethod
    def build_terminal_replay(
        job: JobRecord,
        fault: ConsumedFault,
    ) -> tuple[tuple[CompletionItem, ...], CompletionDecision]:
        payload = {
            'reason': fault.reason,
            'error': fault.error_message or _DEFAULT_ERROR_MESSAGE,
            'error_type': 'fault_injection',
            'fault_rule_id': fault.rule_id,
            'fault_task_id': fault.task_id,
            'fault_remaining_count': fault.remaining_count,
            'fault_injected': True,
        }
        cursor = CompletionCursor(
            source_kind=CompletionSourceKind.STRUCTURED_RESULT_STREAM,
            event_seq=1,
            updated_at=fault.injected_at,
        )
        item = CompletionItem(
            kind=CompletionItemKind.ERROR,
            timestamp=fault.injected_at,
            cursor=cursor,
            provider=job.provider,
            agent_name=job.agent_name,
            req_id=job.job_id,
            payload=payload,
        )
        decision = CompletionDecision(
            terminal=True,
            status=CompletionStatus.FAILED,
            reason=fault.reason,
            confidence=CompletionConfidence.EXACT,
            reply='',
            anchor_seen=False,
            reply_started=False,
            reply_stable=False,
            provider_turn_ref=fault.rule_id,
            source_cursor=cursor,
            finished_at=fault.injected_at,
            diagnostics=dict(payload),
        )
        return ((item,), decision)

    def _new_id(self, prefix: str) -> str:
        return f'{prefix}_{uuid4().hex[:12]}'


__all__ = ['ConsumedFault', 'FaultInjectionService']
