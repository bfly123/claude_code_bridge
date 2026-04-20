from __future__ import annotations

from pathlib import Path

from ..parsing import extract_assistant_blocks, extract_conversation_pairs, strip_ansi
from .state import resolve_log_path


def latest_reader_message(reader) -> str | None:
    clean = _read_clean_log(resolve_log_path(reader))
    if clean is None:
        return None
    blocks = extract_assistant_blocks(clean)
    return blocks[-1] if blocks else None


def latest_conversation_pairs(reader, *, n: int = 1):
    clean = _read_clean_log(resolve_log_path(reader))
    if clean is None:
        return []
    pairs = extract_conversation_pairs(clean)
    return pairs[-max(1, int(n)) :]


def _read_clean_log(log_path: Path | None) -> str | None:
    if log_path is None or not log_path.exists():
        return None
    try:
        raw = log_path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None
    return strip_ansi(raw)


__all__ = ["latest_conversation_pairs", "latest_reader_message"]
