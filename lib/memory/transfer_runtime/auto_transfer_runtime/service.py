from __future__ import annotations

from pathlib import Path

from runtime_env import env_bool

from .matching import is_current_work_dir
from .state import auto_transfer_key, claim_auto_transfer
from .worker import start_transfer_thread


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
        normalized_work_dir = Path(work_dir).expanduser()
    except Exception:
        normalized_work_dir = Path.cwd()
    if not is_current_work_dir(normalized_work_dir):
        return
    key = auto_transfer_key(provider, normalized_work_dir, session_path, session_id, project_id)
    if not claim_auto_transfer(key):
        return
    start_transfer_thread(
        provider=provider,
        work_dir=normalized_work_dir,
        session_path=session_path,
        session_id=session_id,
        project_id=project_id,
    )


__all__ = ['maybe_auto_transfer']
