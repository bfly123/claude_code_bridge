from __future__ import annotations

import os
import sys


def debug_enabled() -> bool:
    return os.environ.get("CCB_DEBUG") in ("1", "true", "yes")


def debug(message: str) -> None:
    if not debug_enabled():
        return
    print(f"[DEBUG] {message}", file=sys.stderr)


__all__ = ["debug", "debug_enabled"]
