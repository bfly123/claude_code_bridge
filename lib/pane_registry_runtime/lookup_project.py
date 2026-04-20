from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import path_is_same_or_parent, provider_pane_alive
from .lookup_records import iter_fresh_registry_records


def latest_project_registry_record(
    *,
    project_id: str,
    qualified_provider: str,
    requested_work_dir: str | None,
    get_backend_for_session_fn,
    compute_project_id_fn,
) -> tuple[dict[str, Any], bool] | None:
    best: tuple[dict[str, Any], bool] | None = None
    best_ts = -1
    registry_work_dir = requested_work_dir or Path.cwd()
    for data, updated_at in iter_fresh_registry_records(work_dir=registry_work_dir):
        match = match_project_registry_record(
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


def match_project_registry_record(
    data: dict[str, Any],
    *,
    project_id: str,
    qualified_provider: str,
    requested_work_dir: str | None,
    get_backend_for_session_fn,
    compute_project_id_fn,
) -> tuple[str, bool] | None:
    existing_project_id = existing_project_id_from_record(data)
    inferred_project_id = inferred_project_id_from_record(data, compute_project_id_fn=compute_project_id_fn)
    effective_project_id = existing_project_id or inferred_project_id
    if effective_project_id != project_id:
        return None
    if requested_work_dir and not matches_requested_work_dir(data, requested_work_dir=requested_work_dir):
        return None
    if not provider_pane_alive(
        data,
        qualified_provider,
        get_backend_for_session_fn=get_backend_for_session_fn,
    ):
        return None
    return effective_project_id, (not existing_project_id) and bool(inferred_project_id)


def existing_project_id_from_record(data: dict[str, Any]) -> str:
    return str(data.get('ccb_project_id') or '').strip()


def inferred_project_id_from_record(data: dict[str, Any], *, compute_project_id_fn) -> str:
    work_dir_value = record_work_dir(data)
    if not work_dir_value:
        return ''
    try:
        return compute_project_id_fn(Path(work_dir_value))
    except Exception:
        return ''


def matches_requested_work_dir(data: dict[str, Any], *, requested_work_dir: str) -> bool:
    return path_is_same_or_parent(record_work_dir(data), requested_work_dir)


def record_work_dir(data: dict[str, Any]) -> str:
    return str(data.get('work_dir') or '').strip()


def migrate_project_id(
    record: dict[str, Any],
    *,
    compute_project_id_fn,
    upsert_registry_fn,
) -> None:
    if existing_project_id_from_record(record):
        return
    work_dir_value = record_work_dir(record)
    if not work_dir_value:
        return
    record['ccb_project_id'] = compute_project_id_fn(Path(work_dir_value))
    if upsert_registry_fn is None:
        from .writes import upsert_registry as default_upsert_registry

        upsert_registry_fn = default_upsert_registry
    upsert_registry_fn(record)


__all__ = [
    'latest_project_registry_record',
    'migrate_project_id',
]
