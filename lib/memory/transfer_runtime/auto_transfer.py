from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from env_utils import env_bool, env_int

_AUTO_TRANSFER_LOCK = threading.Lock()
_AUTO_TRANSFER_SEEN: dict[str, float] = {}


def _normalize_path_for_match(value: Path) -> str:
    try:
        from project_id import normalize_work_dir
    except Exception:
        normalize_work_dir = None
    try:
        if normalize_work_dir:
            return normalize_work_dir(value)
    except Exception:
        pass
    try:
        return str(Path(value).expanduser().resolve())
    except Exception:
        try:
            return str(Path(value).expanduser().absolute())
        except Exception:
            return str(value)


def _is_current_work_dir(work_dir: Path) -> bool:
    try:
        cwd = Path.cwd()
    except Exception:
        cwd = Path(".")
    return _normalize_path_for_match(cwd) == _normalize_path_for_match(work_dir)


def _auto_transfer_key(
    provider: str,
    work_dir: Path,
    session_path: Path | None,
    session_id: str | None,
    project_id: str | None,
) -> str:
    return f"{provider}::{work_dir}::{session_path or ''}::{session_id or ''}::{project_id or ''}"


def maybe_auto_transfer(
    *,
    provider: str,
    work_dir: Path,
    session_path: Path | None = None,
    session_id: str | None = None,
    project_id: str | None = None,
) -> None:
    if not env_bool("CCB_CTX_TRANSFER_ON_SESSION_SWITCH", True):
        return
    if not session_path and not session_id:
        return
    try:
        work_dir = Path(work_dir).expanduser()
    except Exception:
        work_dir = Path.cwd()

    if not _is_current_work_dir(work_dir):
        return

    key = _auto_transfer_key(provider, work_dir, session_path, session_id, project_id)
    now = time.time()
    with _AUTO_TRANSFER_LOCK:
        if key in _AUTO_TRANSFER_SEEN:
            return
        for existing_key, ts in list(_AUTO_TRANSFER_SEEN.items()):
            if now - ts > 3600:
                _AUTO_TRANSFER_SEEN.pop(existing_key, None)
        _AUTO_TRANSFER_SEEN[key] = now

    def _run() -> None:
        try:
            from memory import ContextTransfer
        except Exception:
            return
        try:
            last_n = env_int("CCB_CTX_TRANSFER_LAST_N", 0)
            max_tokens = env_int("CCB_CTX_TRANSFER_MAX_TOKENS", 8000)
            fmt = (os.environ.get("CCB_CTX_TRANSFER_FORMAT") or "markdown").strip().lower() or "markdown"
            target_provider = (os.environ.get("CCB_CTX_TRANSFER_PROVIDER") or "auto").strip().lower() or "auto"
        except Exception:
            last_n = 3
            max_tokens = 8000
            fmt = "markdown"
            target_provider = "auto"

        try:
            transfer = ContextTransfer(max_tokens=max_tokens, work_dir=work_dir)
            context = transfer.extract_conversations(
                session_path=session_path,
                last_n=last_n,
                source_provider=provider,
                source_session_id=session_id,
                source_project_id=project_id,
            )
            if not context.conversations:
                return
            ts = time.strftime("%Y%m%d-%H%M%S")
            sid = (session_id or (session_path.stem if session_path else "")) or "unknown"
            filename = f"{provider}-{ts}-{sid}"
            transfer.save_transfer(context, fmt, target_provider, filename=filename)
        except Exception:
            return

    threading.Thread(target=_run, daemon=True).start()
