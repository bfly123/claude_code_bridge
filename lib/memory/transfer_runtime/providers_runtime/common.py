from __future__ import annotations

from pathlib import Path
from typing import Optional

from memory.types import TransferContext

from ..conversations import context_from_pairs


def expand_optional_path(raw) -> Optional[Path]:
    if not raw:
        return None
    try:
        return Path(str(raw)).expanduser()
    except Exception:
        return None


def fetch_count(*, last_n: int, fallback_pairs: int) -> int:
    return last_n if last_n > 0 else fallback_pairs


def resolved_session_id(*, session_id: Optional[str], session_path: Optional[Path]) -> str:
    candidate = str(session_id or '').strip()
    if not candidate and session_path is not None:
        try:
            candidate = session_path.stem
        except Exception:
            candidate = ''
    return candidate or 'unknown'


def build_transfer_context(
    *,
    deduper,
    formatter,
    max_tokens: int,
    pairs,
    provider: str,
    session_id: str,
    session_path: Optional[Path],
    last_n: int,
) -> TransferContext:
    return context_from_pairs(
        deduper=deduper,
        formatter=formatter,
        max_tokens=max_tokens,
        pairs=pairs,
        provider=provider,
        session_id=session_id,
        session_path=session_path,
        last_n=last_n,
    )
