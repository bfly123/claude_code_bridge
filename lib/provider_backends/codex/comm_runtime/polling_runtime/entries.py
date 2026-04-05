from __future__ import annotations

import json
import os
import time
from typing import Any, Callable


Extractor = Callable[[dict[str, Any]], Any | None]


def read_matching_from_handle(
    handle,
    offset: int,
    *,
    extractor: Extractor,
    deadline: float,
    block: bool,
) -> tuple[Any | None, int]:
    while True:
        if block and time.time() >= deadline:
            return None, offset
        pos_before = handle.tell()
        raw_line = handle.readline()
        if not raw_line:
            return None, offset
        if not raw_line.endswith(b"\n"):
            handle.seek(pos_before, os.SEEK_SET)
            return None, offset
        offset = handle.tell()
        line = raw_line.decode("utf-8", errors="ignore").strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        match = extractor(entry)
        if match is not None:
            return match, offset


__all__ = ["Extractor", "read_matching_from_handle"]
