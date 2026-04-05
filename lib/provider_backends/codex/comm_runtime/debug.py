from __future__ import annotations

import os
import sys

from env_utils import env_int


def debug_enabled() -> bool:
    return os.environ.get("CCB_DEBUG") in ("1", "true", "yes") or os.environ.get("CPEND_DEBUG") in (
        "1",
        "true",
        "yes",
    )


def debug_log_reader(message: str) -> None:
    if not debug_enabled():
        return
    print(f"[DEBUG] {message}", file=sys.stderr)

__all__ = ["debug_enabled", "debug_log_reader", "env_int"]
