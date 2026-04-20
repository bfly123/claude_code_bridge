from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from runtime_env import env_int


def start_transfer_thread(
    *,
    provider: str,
    work_dir: Path,
    session_path: Path | None,
    session_id: str | None,
    project_id: str | None,
) -> None:
    threading.Thread(
        target=_run_transfer_target(
            provider=provider,
            work_dir=work_dir,
            session_path=session_path,
            session_id=session_id,
            project_id=project_id,
        ),
        daemon=True,
    ).start()


def run_transfer(
    *,
    provider: str,
    work_dir: Path,
    session_path: Path | None,
    session_id: str | None,
    project_id: str | None,
) -> None:
    context_transfer_cls = _context_transfer_cls()
    if context_transfer_cls is None:
        return
    last_n, max_tokens, fmt, target_provider = _transfer_settings()

    try:
        transfer = context_transfer_cls(max_tokens=max_tokens, work_dir=work_dir)
        context = transfer.extract_conversations(
            session_path=session_path,
            last_n=last_n,
            source_provider=provider,
            source_session_id=session_id,
            source_project_id=project_id,
        )
        if not context.conversations:
            return
        transfer.save_transfer(
            context,
            fmt,
            target_provider,
            filename=_transfer_filename(
                provider,
                session_path=session_path,
                session_id=session_id,
            ),
        )
    except Exception:
        return


def _run_transfer_target(
    *,
    provider: str,
    work_dir: Path,
    session_path: Path | None,
    session_id: str | None,
    project_id: str | None,
):
    return lambda: run_transfer(
        provider=provider,
        work_dir=work_dir,
        session_path=session_path,
        session_id=session_id,
        project_id=project_id,
    )


def _context_transfer_cls():
    try:
        from memory import ContextTransfer
    except Exception:
        return None
    return ContextTransfer


def _transfer_settings() -> tuple[int, int, str, str]:
    try:
        return (
            env_int("CCB_CTX_TRANSFER_LAST_N", 0),
            env_int("CCB_CTX_TRANSFER_MAX_TOKENS", 8000),
            _normalized_env("CCB_CTX_TRANSFER_FORMAT", default="markdown"),
            _normalized_env("CCB_CTX_TRANSFER_PROVIDER", default="auto"),
        )
    except Exception:
        return 3, 8000, "markdown", "auto"


def _normalized_env(name: str, *, default: str) -> str:
    value = (os.environ.get(name) or default).strip().lower()
    return value or default


def _transfer_filename(provider: str, *, session_path: Path | None, session_id: str | None) -> str:
    ts = time.strftime("%Y%m%d-%H%M%S")
    sid = (session_id or (session_path.stem if session_path else "")) or "unknown"
    return f"{provider}-{ts}-{sid}"


__all__ = ['run_transfer', 'start_transfer_thread']
