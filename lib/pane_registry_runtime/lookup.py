from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from project.identity import compute_ccb_project_id
from terminal_runtime import get_backend_for_session

from .common import (
    coerce_updated_at,
    debug,
    get_providers_map,
    is_stale,
    iter_registry_files,
    load_registry_file,
    path_is_same_or_parent,
    provider_pane_alive,
    registry_path_for_session,
)


def load_registry_by_session_id(session_id: str) -> Optional[Dict[str, Any]]:
    if not session_id:
        return None
    path = registry_path_for_session(session_id, work_dir=Path.cwd())
    record = _load_fresh_registry(
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
    best = _latest_registry_record(
        record
        for record in _iter_fresh_registry_records(
            work_dir=Path.cwd(),
            stale_debug_message_fn=lambda path: f"Registry stale for pane {pane_id}: {path}",
        )
        if _claude_pane_id(record[0]) == pane_id
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

    best = _latest_project_registry_record(
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
            _migrate_project_id(
                best_record,
                compute_project_id_fn=compute_project_id_fn,
                upsert_registry_fn=upsert_registry_fn,
            )
        except Exception:
            pass

    return best_record


def _load_fresh_registry(
    path: Path,
    *,
    stale_debug_message: str | None = None,
) -> tuple[Dict[str, Any], int] | None:
    if not path.exists():
        return None
    data = load_registry_file(path)
    if not data:
        return None
    updated_at = coerce_updated_at(data.get("updated_at"), path)
    if is_stale(updated_at):
        if stale_debug_message:
            debug(stale_debug_message)
        return None
    return data, updated_at


def _iter_fresh_registry_records(
    *,
    work_dir: str | Path | None = None,
    stale_debug_message_fn=None,
):
    for path in iter_registry_files(work_dir=work_dir):
        stale_debug_message = stale_debug_message_fn(path) if callable(stale_debug_message_fn) else None
        record = _load_fresh_registry(path, stale_debug_message=stale_debug_message)
        if record is not None:
            yield record


def _latest_registry_record(records) -> tuple[Dict[str, Any], int] | None:
    best: tuple[Dict[str, Any], int] | None = None
    best_ts = -1
    for data, updated_at in records:
        if updated_at > best_ts:
            best = (data, updated_at)
            best_ts = updated_at
    return best


def _claude_pane_id(data: Dict[str, Any]) -> str | None:
    providers = get_providers_map(data)
    claude = providers.get("claude")
    if not isinstance(claude, dict):
        return None
    pane_id = str(claude.get("pane_id") or "").strip()
    return pane_id or None


def _latest_project_registry_record(
    *,
    project_id: str,
    qualified_provider: str,
    requested_work_dir: str | None,
    get_backend_for_session_fn,
    compute_project_id_fn,
) -> tuple[Dict[str, Any], bool] | None:
    best: tuple[Dict[str, Any], bool] | None = None
    best_ts = -1
    registry_work_dir = requested_work_dir or Path.cwd()
    for data, updated_at in _iter_fresh_registry_records(work_dir=registry_work_dir):
        match = _match_project_registry_record(
            data,
            project_id=project_id,
            qualified_provider=qualified_provider,
            requested_work_dir=requested_work_dir,
            get_backend_for_session_fn=get_backend_for_session_fn,
            compute_project_id_fn=compute_project_id_fn,
        )
        if match is None:
            continue
        _, needs_migration = match
        if updated_at > best_ts:
            best = (data, needs_migration)
            best_ts = updated_at
    return best


def _match_project_registry_record(
    data: Dict[str, Any],
    *,
    project_id: str,
    qualified_provider: str,
    requested_work_dir: str | None,
    get_backend_for_session_fn,
    compute_project_id_fn,
) -> tuple[str, bool] | None:
    existing_project_id = _existing_project_id(data)
    inferred_project_id = _inferred_project_id(data, compute_project_id_fn=compute_project_id_fn)
    effective_project_id = existing_project_id or inferred_project_id
    if effective_project_id != project_id:
        return None
    if requested_work_dir and not _matches_requested_work_dir(data, requested_work_dir=requested_work_dir):
        return None
    if not provider_pane_alive(
        data,
        qualified_provider,
        get_backend_for_session_fn=get_backend_for_session_fn,
    ):
        return None
    return effective_project_id, (not existing_project_id) and bool(inferred_project_id)


def _existing_project_id(data: Dict[str, Any]) -> str:
    return str(data.get("ccb_project_id") or "").strip()


def _inferred_project_id(data: Dict[str, Any], *, compute_project_id_fn) -> str:
    work_dir_value = _record_work_dir(data)
    if not work_dir_value:
        return ""
    try:
        return compute_project_id_fn(Path(work_dir_value))
    except Exception:
        return ""


def _matches_requested_work_dir(data: Dict[str, Any], *, requested_work_dir: str) -> bool:
    return path_is_same_or_parent(_record_work_dir(data), requested_work_dir)


def _record_work_dir(data: Dict[str, Any]) -> str:
    return str(data.get("work_dir") or "").strip()


def _migrate_project_id(
    record: Dict[str, Any],
    *,
    compute_project_id_fn,
    upsert_registry_fn,
) -> None:
    if _existing_project_id(record):
        return
    work_dir_value = _record_work_dir(record)
    if not work_dir_value:
        return
    record["ccb_project_id"] = compute_project_id_fn(Path(work_dir_value))
    if upsert_registry_fn is None:
        from .writes import upsert_registry as default_upsert_registry

        upsert_registry_fn = default_upsert_registry
    upsert_registry_fn(record)
