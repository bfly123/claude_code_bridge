from __future__ import annotations

import os
import re

from provider_core.protocol import ANY_REQ_ID_PATTERN, REQ_ID_BOUNDARY_PATTERN, REQ_ID_PREFIX


REQ_ID_RE = re.compile(
    rf"{re.escape(REQ_ID_PREFIX)}\s*({ANY_REQ_ID_PATTERN}){REQ_ID_BOUNDARY_PATTERN}",
    re.IGNORECASE,
)


def bounded_poll_interval() -> float:
    try:
        poll = float(os.environ.get("OPENCODE_POLL_INTERVAL", "0.05"))
    except Exception:
        poll = 0.05
    return min(0.5, max(0.02, poll))


def bounded_force_read_interval() -> float:
    try:
        force = float(os.environ.get("OPENCODE_FORCE_READ_INTERVAL", "1.0"))
    except Exception:
        force = 1.0
    return min(5.0, max(0.2, force))


__all__ = ['REQ_ID_RE', 'bounded_force_read_interval', 'bounded_poll_interval']
