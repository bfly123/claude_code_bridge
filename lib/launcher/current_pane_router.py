from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class LauncherCurrentPaneRouter:
    translate_fn: Callable[..., str]

    def start(
        self,
        provider: str,
        *,
        display_label: str | None = None,
        starters: dict[str, Callable[[], int]],
    ) -> int:
        key = (provider or '').strip().lower()
        starter = starters.get(key)
        if starter is None:
            print(f"❌ {self.translate_fn('unknown_provider', provider=display_label or provider)}")
            return 1
        return starter()
