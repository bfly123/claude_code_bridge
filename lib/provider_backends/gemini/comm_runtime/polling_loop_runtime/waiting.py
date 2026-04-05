from __future__ import annotations

import time
from pathlib import Path

from .context import GeminiPollingCursor, current_state_payload


def wait_or_timeout(
    reader,
    *,
    cursor: GeminiPollingCursor,
    session: Path | None,
):
    time.sleep(reader._poll_interval)
    if time.time() < cursor.deadline:
        return None
    return None, current_state_payload(cursor, session=session)


__all__ = ["wait_or_timeout"]
