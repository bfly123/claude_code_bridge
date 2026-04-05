from __future__ import annotations

from typing import Protocol

from completion.models import CompletionCursor, CompletionItem


class CompletionSource(Protocol):
    def capture_baseline(self) -> CompletionCursor: ...

    def poll(self, cursor: CompletionCursor, timeout_s: float) -> CompletionItem | None: ...
