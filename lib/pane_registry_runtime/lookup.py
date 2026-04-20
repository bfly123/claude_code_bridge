from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from project.identity import compute_ccb_project_id
from terminal_runtime import get_backend_for_session

from .common import registry_path_for_session
from .lookup_project import latest_project_registry_record, migrate_project_id
from .lookup_records import claude_pane_id, iter_fresh_registry_records, latest_registry_record, load_fresh_registry


def load_registry_by_session_id(session_id: str) -> Optional[Dict[str, Any]]:
    if not session_id:
        return None
    path = registry_path_for_session(session_id, work_dir=Path.cwd())
    record = load_fresh_registry(
        path,
        stale_debug_message=f"Registry stale for session {session_id}: {path}",
    )
    return record[0] if record is not None else None


def load_registry_by_claude_pane(
    pane_id: str,
    *,
    get_backend_for_session_fn=get_backend_for_session,
) -> Optional[Dict[str, Any]]:
    del get_backend_for_session_fn
    if not pane_id:
        return None
    best = latest_registry_record(
        record
        for record in iter_fresh_registry_records(
            work_dir=Path.cwd(),
            stale_debug_message_fn=lambda path: f"Registry stale for pane {pane_id}: {path}",
        )
        if claude_pane_id(record[0]) == pane_id
    )
    return best[0] if best is not None else None


def load_registry_by_project_id(
    ccb_project_id: str,
    provider: str,
    *,
    work_dir: str | Path | None = None,
    get_backend_for_session_fn=get_backend_for_session,
    compute_project_id_fn=compute_ccb_project_id,
    upsert_registry_fn=None,
) -> Optional[Dict[str, Any]]:
    """
    Load the newest alive registry record matching `{ccb_project_id, provider}`.

    This enforces directory isolation and avoids parent-directory pollution.
    """
    project_id = (ccb_project_id or "").strip()
    qualified_provider = (provider or "").strip().lower()
    requested_work_dir = str(work_dir) if work_dir is not None else None
    if not project_id or not qualified_provider:
        return None

    best = latest_project_registry_record(
        project_id=project_id,
        qualified_provider=qualified_provider,
        requested_work_dir=requested_work_dir,
        get_backend_for_session_fn=get_backend_for_session_fn,
        compute_project_id_fn=compute_project_id_fn,
    )
    if best is None:
        return None
    best_record, best_needs_migration = best
    if best_needs_migration:
        try:
            migrate_project_id(
                best_record,
                compute_project_id_fn=compute_project_id_fn,
                upsert_registry_fn=upsert_registry_fn,
            )
        except Exception:
            pass

    return best_record
