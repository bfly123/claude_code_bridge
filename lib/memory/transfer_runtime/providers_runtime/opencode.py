from __future__ import annotations

from pathlib import Path
from typing import Optional

from memory.types import SessionNotFoundError, TransferContext

from ..conversations import load_session_data
from .common import build_transfer_context, expand_optional_path, fetch_count, resolved_session_id


def extract_from_opencode(
    *,
    work_dir: Path,
    source_session_files: dict[str, str],
    deduper,
    formatter,
    max_tokens: int,
    fallback_pairs: int,
    last_n: int,
    session_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> TransferContext:
    _session_file, data = load_session_data(work_dir, source_session_files, 'opencode')
    resolved_session_id_value = _opencode_session_id(data, session_id=session_id)
    resolved_project_id = _opencode_project_id(data, project_id=project_id)

    from provider_backends.opencode.comm import OpenCodeLogReader

    log_reader = OpenCodeLogReader(
        work_dir=work_dir,
        project_id=resolved_project_id or 'global',
        session_id_filter=resolved_session_id_value or None,
    )

    resolved_session_id_value, resolved_session_path = _resolve_opencode_session_identity(
        log_reader,
        session_id=resolved_session_id_value,
    )

    pairs = _opencode_pairs(
        log_reader,
        session_id=resolved_session_id_value,
        fetch_n=fetch_count(last_n=last_n, fallback_pairs=fallback_pairs),
    )
    return build_transfer_context(
        deduper=deduper,
        formatter=formatter,
        max_tokens=max_tokens,
        pairs=pairs,
        provider='opencode',
        session_id=resolved_session_id_value or 'unknown',
        session_path=resolved_session_path,
        last_n=last_n,
    )


def _opencode_session_id(data: dict, *, session_id: Optional[str]) -> str:
    return str(
        session_id or data.get('opencode_session_id') or data.get('opencode_storage_session_id') or ''
    ).strip()


def _opencode_project_id(data: dict, *, project_id: Optional[str]) -> str:
    return str(project_id or data.get('opencode_project_id') or '').strip()


def _resolve_opencode_session_identity(
    log_reader,
    *,
    session_id: str,
) -> tuple[str, Optional[Path]]:
    if session_id:
        return session_id, None
    state = log_reader.capture_state()
    resolved_session_path = expand_optional_path(state.get('session_path'))
    resolved_session_id_value = resolved_session_id(
        session_id=str(state.get('session_id') or '').strip(),
        session_path=resolved_session_path,
    )
    if resolved_session_id_value == 'unknown':
        raise SessionNotFoundError('No OpenCode session found')
    return resolved_session_id_value, resolved_session_path


def _opencode_pairs(log_reader, *, session_id: str, fetch_n: int):
    if hasattr(log_reader, 'conversations_for_session') and session_id:
        return log_reader.conversations_for_session(session_id, fetch_n)
    return log_reader.latest_conversations(fetch_n)
