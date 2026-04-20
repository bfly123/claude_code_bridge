from __future__ import annotations

from pathlib import Path
from typing import Optional

from memory.types import SessionNotFoundError, TransferContext

from ..conversations import load_session_data
from .common import build_transfer_context, expand_optional_path, fetch_count, resolved_session_id


def extract_from_droid(
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
    _session_file, data = load_session_data(work_dir, source_session_files, 'droid')
    resolved_session_id_value = str(session_id or data.get('droid_session_id') or '').strip()
    preferred_path = expand_optional_path(session_path or data.get('droid_session_path'))

    from provider_backends.droid.comm import DroidLogReader

    log_reader = DroidLogReader(work_dir=work_dir)
    if preferred_path and preferred_path.exists():
        log_reader.set_preferred_session(preferred_path)
    if resolved_session_id_value:
        log_reader.set_session_id_hint(resolved_session_id_value)

    resolved_session_path = log_reader.current_session_path()
    if not resolved_session_path or not resolved_session_path.exists():
        raise SessionNotFoundError('No Droid session found')

    pairs = log_reader.latest_conversations(fetch_count(last_n=last_n, fallback_pairs=fallback_pairs))
    return build_transfer_context(
        deduper=deduper,
        formatter=formatter,
        max_tokens=max_tokens,
        pairs=pairs,
        provider='droid',
        session_id=resolved_session_id(session_id=resolved_session_id_value, session_path=resolved_session_path),
        session_path=resolved_session_path,
        last_n=last_n,
    )
