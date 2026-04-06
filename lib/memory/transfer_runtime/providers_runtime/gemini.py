from __future__ import annotations

from pathlib import Path
from typing import Optional

from memory.types import SessionNotFoundError, TransferContext

from ..conversations import load_session_data
from .common import build_transfer_context, expand_optional_path, fetch_count, resolved_session_id


def extract_from_gemini(
    *,
    work_dir: Path,
    source_session_files: dict[str, str],
    deduper,
    formatter,
    max_tokens: int,
    fallback_pairs: int,
    last_n: int,
    session_path: Optional[Path] = None,
    session_id: Optional[str] = None,
) -> TransferContext:
    _session_file, data = load_session_data(work_dir, source_session_files, 'gemini')
    resolved_session_id_value = str(session_id or data.get('gemini_session_id') or '').strip()
    preferred_path = expand_optional_path(session_path or data.get('gemini_session_path'))

    from provider_backends.gemini.comm import GeminiLogReader

    log_reader = GeminiLogReader(work_dir=work_dir)
    if preferred_path and preferred_path.exists():
        log_reader.set_preferred_session(preferred_path)

    resolved_session_path = log_reader._latest_session()
    if not resolved_session_path or not resolved_session_path.exists():
        raise SessionNotFoundError('No Gemini session found')

    pairs = log_reader.latest_conversations(fetch_count(last_n=last_n, fallback_pairs=fallback_pairs))
    return build_transfer_context(
        deduper=deduper,
        formatter=formatter,
        max_tokens=max_tokens,
        pairs=pairs,
        provider='gemini',
        session_id=resolved_session_id(session_id=resolved_session_id_value, session_path=resolved_session_path),
        session_path=resolved_session_path,
        last_n=last_n,
    )
