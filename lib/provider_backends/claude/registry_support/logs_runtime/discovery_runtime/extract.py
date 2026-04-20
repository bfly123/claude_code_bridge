from __future__ import annotations

import re


SESSION_ID_PATTERN = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    re.IGNORECASE,
)


def extract_session_id_from_start_cmd(start_cmd: str) -> str | None:
    if not start_cmd:
        return None
    match = SESSION_ID_PATTERN.search(start_cmd)
    if not match:
        return None
    return match.group(0)


__all__ = ['extract_session_id_from_start_cmd']
