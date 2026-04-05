from __future__ import annotations

from typing import Protocol

from completion.models import CompletionDecision, ReplyCandidate


class ReplySelector(Protocol):
    def ingest_candidate(self, candidate: ReplyCandidate) -> None: ...

    def select(self, decision: CompletionDecision) -> str: ...

    def preview(self) -> str: ...

    def reset(self) -> None: ...


class BaseReplySelector:
    def __init__(self) -> None:
        self._candidates: list[tuple[int, ReplyCandidate]] = []
        self._sequence = 0

    def ingest_candidate(self, candidate: ReplyCandidate) -> None:
        self._candidates.append((self._sequence, candidate))
        self._sequence += 1

    def reset(self) -> None:
        self._candidates.clear()

    def select(self, decision: CompletionDecision) -> str:
        if not decision.terminal:
            raise ValueError('cannot select reply before terminal decision')
        if decision.reply:
            return decision.reply
        best = self._best_candidate()
        return best.text if best is not None else ''

    def preview(self) -> str:
        best = self._best_candidate()
        return best.text if best is not None else ''

    def _best_candidate(self) -> ReplyCandidate | None:
        if not self._candidates:
            return None
        return sorted(
            self._candidates,
            key=lambda entry: (entry[1].priority or 999, -(entry[0])),
        )[0][1]
