from __future__ import annotations

import os
from pathlib import Path

from ..debug import debug_log_reader


def iter_lines_reverse(reader, log_path: Path, *, max_bytes: int, max_lines: int) -> list[str]:
    del reader
    if max_bytes <= 0 or max_lines <= 0:
        return []
    try:
        with log_path.open("rb") as handle:
            return read_tail_lines(handle, max_bytes=max_bytes, max_lines=max_lines)
    except OSError as exc:
        debug_log_reader(f"Failed reading log tail: {log_path} ({exc})")
        return []


def read_tail_lines(handle, *, max_bytes: int, max_lines: int) -> list[str]:
    handle.seek(0, os.SEEK_END)
    position = handle.tell()
    bytes_read = 0
    lines: list[str] = []
    buffer = b""

    while position > 0 and bytes_read < max_bytes and len(lines) < max_lines:
        position, chunk = read_tail_chunk(handle, position=position, bytes_read=bytes_read, max_bytes=max_bytes)
        bytes_read += len(chunk)
        buffer = chunk + buffer
        buffer = collect_lines(buffer, lines, max_lines=max_lines)

    if position == 0 and buffer and len(lines) < max_lines:
        append_decoded_line(lines, buffer, max_lines=max_lines)
    return lines


def read_tail_chunk(handle, *, position: int, bytes_read: int, max_bytes: int) -> tuple[int, bytes]:
    remaining = max_bytes - bytes_read
    read_size = min(8192, position, remaining)
    position -= read_size
    handle.seek(position, os.SEEK_SET)
    return position, handle.read(read_size)


def collect_lines(buffer: bytes, lines: list[str], *, max_lines: int) -> bytes:
    parts = buffer.split(b"\n")
    next_buffer = parts[0]
    for part in reversed(parts[1:]):
        if len(lines) >= max_lines:
            break
        append_decoded_line(lines, part, max_lines=max_lines)
    return next_buffer


def append_decoded_line(lines: list[str], payload: bytes, *, max_lines: int) -> None:
    if len(lines) >= max_lines:
        return
    text = payload.decode("utf-8", errors="ignore").strip()
    if text:
        lines.append(text)


__all__ = ["iter_lines_reverse"]
