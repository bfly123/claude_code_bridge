from __future__ import annotations

import time
from typing import Callable

from completion.detectors.base import CompletionDetector
from completion.models import CompletionDecision, CompletionRequestContext, reply_candidates_from_item, utc_now_iso
from completion.selectors.base import ReplySelector
from completion.sources.base import CompletionSource


class CompletionOrchestrator:
    def __init__(self, *, now_factory: Callable[[], str] | None = None) -> None:
        self._now_factory = now_factory or utc_now_iso

    def run(
        self,
        request_ctx: CompletionRequestContext,
        source: CompletionSource,
        detector: CompletionDetector,
        selector: ReplySelector,
    ) -> CompletionDecision:
        baseline = source.capture_baseline()
        detector.bind(request_ctx, baseline)
        cursor = baseline
        deadline = time.monotonic() + request_ctx.timeout_s

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            item = source.poll(cursor, min(request_ctx.poll_interval_s, remaining))
            if item is None:
                if hasattr(detector, 'tick'):
                    detector.tick(self._now_factory(), cursor)
                decision = detector.decision()
                if decision.terminal:
                    return self._finalize(selector, decision)
                continue

            cursor = item.cursor
            for candidate in reply_candidates_from_item(item):
                selector.ingest_candidate(candidate)
            detector.ingest(item)
            decision = detector.decision()
            if decision.terminal:
                return self._finalize(selector, decision)

        if hasattr(detector, 'finalize_timeout'):
            detector.finalize_timeout(self._now_factory(), cursor)
        decision = detector.decision()
        return self._finalize(selector, decision)

    def _finalize(self, selector: ReplySelector, decision: CompletionDecision) -> CompletionDecision:
        if not decision.terminal:
            return decision
        reply = selector.select(decision)
        if reply and not decision.reply:
            return decision.with_reply(reply)
        return decision
