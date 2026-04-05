from __future__ import annotations

from pathlib import Path
from typing import Optional

from memory.types import SessionNotFoundError, TransferContext

from .conversations import context_from_pairs, load_session_data


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
    _session_file, data = load_session_data(work_dir, source_session_files, "codex")
    log_path = session_path or data.get("codex_session_path") or data.get("session_path")
    session_id = session_id or data.get("codex_session_id") or ""
    log_path_obj: Optional[Path] = None
    if log_path:
        try:
            log_path_obj = Path(str(log_path)).expanduser()
        except Exception:
            log_path_obj = None

    from provider_backends.codex.comm import CodexLogReader

    log_reader = CodexLogReader(
        log_path=log_path_obj if log_path_obj and log_path_obj.exists() else None,
        session_id_filter=session_id or None,
        work_dir=work_dir,
    )
    scan_path = log_reader._latest_log()
    if not scan_path or not scan_path.exists():
        raise SessionNotFoundError("No Codex session log found")

    fetch_n = last_n if last_n > 0 else fallback_pairs
    pairs = log_reader.latest_conversations(fetch_n)
    resolved_session_path = log_path_obj if log_path_obj and log_path_obj.exists() else scan_path
    if not session_id and resolved_session_path:
        session_id = resolved_session_path.stem
    if not session_id:
        session_id = "unknown"

    return context_from_pairs(
        deduper=deduper,
        formatter=formatter,
        max_tokens=max_tokens,
        pairs=pairs,
        provider="codex",
        session_id=session_id,
        session_path=resolved_session_path,
        last_n=last_n,
    )


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
    _session_file, data = load_session_data(work_dir, source_session_files, "gemini")
    session_id = session_id or data.get("gemini_session_id") or ""
    preferred_path = session_path or data.get("gemini_session_path")
    preferred_path_obj: Optional[Path] = None
    if preferred_path:
        try:
            preferred_path_obj = Path(str(preferred_path)).expanduser()
        except Exception:
            preferred_path_obj = None

    from provider_backends.gemini.comm import GeminiLogReader

    log_reader = GeminiLogReader(work_dir=work_dir)
    if preferred_path_obj and preferred_path_obj.exists():
        log_reader.set_preferred_session(preferred_path_obj)

    resolved_session_path = log_reader._latest_session()
    if not resolved_session_path or not resolved_session_path.exists():
        raise SessionNotFoundError("No Gemini session found")

    fetch_n = last_n if last_n > 0 else fallback_pairs
    pairs = log_reader.latest_conversations(fetch_n)
    if not session_id and resolved_session_path:
        session_id = resolved_session_path.stem
    if not session_id:
        session_id = "unknown"

    return context_from_pairs(
        deduper=deduper,
        formatter=formatter,
        max_tokens=max_tokens,
        pairs=pairs,
        provider="gemini",
        session_id=session_id,
        session_path=resolved_session_path,
        last_n=last_n,
    )


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
    _session_file, data = load_session_data(work_dir, source_session_files, "droid")
    session_id = session_id or data.get("droid_session_id") or ""
    preferred_path = session_path or data.get("droid_session_path")
    preferred_path_obj: Optional[Path] = None
    if preferred_path:
        try:
            preferred_path_obj = Path(str(preferred_path)).expanduser()
        except Exception:
            preferred_path_obj = None

    from provider_backends.droid.comm import DroidLogReader

    log_reader = DroidLogReader(work_dir=work_dir)
    if preferred_path_obj and preferred_path_obj.exists():
        log_reader.set_preferred_session(preferred_path_obj)
    if session_id:
        log_reader.set_session_id_hint(session_id)

    resolved_session_path = log_reader.current_session_path()
    if not resolved_session_path or not resolved_session_path.exists():
        raise SessionNotFoundError("No Droid session found")

    fetch_n = last_n if last_n > 0 else fallback_pairs
    pairs = log_reader.latest_conversations(fetch_n)
    if not session_id and resolved_session_path:
        session_id = resolved_session_path.stem
    if not session_id:
        session_id = "unknown"

    return context_from_pairs(
        deduper=deduper,
        formatter=formatter,
        max_tokens=max_tokens,
        pairs=pairs,
        provider="droid",
        session_id=session_id,
        session_path=resolved_session_path,
        last_n=last_n,
    )


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
    _session_file, data = load_session_data(work_dir, source_session_files, "opencode")
    session_id = session_id or data.get("opencode_session_id") or data.get("opencode_storage_session_id") or ""
    project_id = project_id or data.get("opencode_project_id") or ""

    from provider_backends.opencode.comm import OpenCodeLogReader

    log_reader = OpenCodeLogReader(
        work_dir=work_dir,
        project_id=project_id or "global",
        session_id_filter=session_id or None,
    )
    session_path = None
    if not session_id:
        state = log_reader.capture_state()
        session_path = state.get("session_path")
        session_id = state.get("session_id") or ""
        if not session_id and session_path:
            try:
                session_id = Path(session_path).stem
            except Exception:
                session_id = ""
        if not session_id:
            raise SessionNotFoundError("No OpenCode session found")

    fetch_n = last_n if last_n > 0 else fallback_pairs
    if hasattr(log_reader, "conversations_for_session") and session_id:
        pairs = log_reader.conversations_for_session(session_id, fetch_n)
    else:
        pairs = log_reader.latest_conversations(fetch_n)

    session_path_obj: Optional[Path] = None
    if session_path:
        try:
            session_path_obj = session_path if isinstance(session_path, Path) else Path(str(session_path)).expanduser()
        except Exception:
            session_path_obj = None

    return context_from_pairs(
        deduper=deduper,
        formatter=formatter,
        max_tokens=max_tokens,
        pairs=pairs,
        provider="opencode",
        session_id=session_id or "unknown",
        session_path=session_path_obj,
        last_n=last_n,
    )
