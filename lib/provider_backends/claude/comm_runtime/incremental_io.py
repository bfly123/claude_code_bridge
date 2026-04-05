from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_incremental_jsonl(path: Path, offset: int, carry: bytes) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        size = path.stat().st_size
    except OSError:
        return [], {"offset": offset, "carry": carry}

    if size < offset:
        offset = 0
        carry = b""

    try:
        with path.open("rb") as handle:
            handle.seek(offset)
            data = handle.read()
    except OSError:
        return [], {"offset": offset, "carry": carry}

    new_offset = offset + len(data)
    buf = carry + data
    lines = buf.split(b"\n")
    if buf and not buf.endswith(b"\n"):
        carry = lines.pop()
    else:
        carry = b""

    entries: list[dict[str, Any]] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(entry, dict):
            entries.append(entry)

    return entries, {"offset": new_offset, "carry": carry}


__all__ = ["read_incremental_jsonl"]
