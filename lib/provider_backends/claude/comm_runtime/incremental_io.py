from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_incremental_jsonl(
    path: Path,
    offset: int,
    carry: bytes,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    size = _file_size(path)
    if size is None:
        return [], {"offset": offset, "carry": carry}
    offset, carry = _normalized_reader_state(size=size, offset=offset, carry=carry)
    data = _read_bytes(path, offset)
    if data is None:
        return [], {"offset": offset, "carry": carry}
    new_offset = offset + len(data)
    lines, carry = _split_buffer_lines(carry, data)
    entries = _parse_jsonl_entries(lines)
    return entries, {"offset": new_offset, "carry": carry}


def _file_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def _normalized_reader_state(*, size: int, offset: int, carry: bytes) -> tuple[int, bytes]:
    if size < offset:
        return 0, b""
    return offset, carry


def _read_bytes(path: Path, offset: int) -> bytes | None:
    try:
        with path.open("rb") as handle:
            handle.seek(offset)
            return handle.read()
    except OSError:
        return None


def _split_buffer_lines(carry: bytes, data: bytes) -> tuple[list[bytes], bytes]:
    buffer = carry + data
    lines = buffer.split(b"\n")
    if buffer and not buffer.endswith(b"\n"):
        return lines[:-1], lines[-1]
    return lines, b""


def _parse_jsonl_entries(lines: list[bytes]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for raw in lines:
        entry = _parse_jsonl_entry(raw)
        if entry is not None:
            entries.append(entry)
    return entries


def _parse_jsonl_entry(raw: bytes) -> dict[str, Any] | None:
    line = raw.strip()
    if not line:
        return None
    try:
        entry = json.loads(line.decode("utf-8", errors="replace"))
    except Exception:
        return None
    return entry if isinstance(entry, dict) else None


__all__ = ["read_incremental_jsonl"]
