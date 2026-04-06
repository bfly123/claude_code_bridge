from __future__ import annotations

from pathlib import Path
from typing import Optional

from memory.types import SessionNotFoundError, TransferContext

from ..conversations import load_session_data
from .common import build_transfer_context, expand_optional_path, fetch_count, resolved_session_id


def extract_from_codex(
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
    _session_file, data = load_session_data(work_dir, source_session_files, 'codex')
    preferred_path = session_path or data.get('codex_session_path') or data.get('session_path')
    resolved_preferred_path = expand_optional_path(preferred_path)
    resolved_session_id_value = str(session_id or data.get('codex_session_id') or '').strip()

    from provider_backends.codex.comm import CodexLogReader

    log_reader = CodexLogReader(
        log_path=resolved_preferred_path if resolved_preferred_path and resolved_preferred_path.exists() else None,
        session_id_filter=resolved_session_id_value or None,
        work_dir=work_dir,
    )
    scan_path = log_reader._latest_log()
    if not scan_path or not scan_path.exists():
        raise SessionNotFoundError('No Codex session log found')

    pairs = log_reader.latest_conversations(fetch_count(last_n=last_n, fallback_pairs=fallback_pairs))
    resolved_session_path = resolved_preferred_path if resolved_preferred_path and resolved_preferred_path.exists() else scan_path
    return build_transfer_context(
        deduper=deduper,
        formatter=formatter,
        max_tokens=max_tokens,
        pairs=pairs,
        provider='codex',
        session_id=resolved_session_id(session_id=resolved_session_id_value, session_path=resolved_session_path),
        session_path=resolved_session_path,
        last_n=last_n,
    )
