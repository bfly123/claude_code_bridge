from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from project_id import compute_ccb_project_id
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
    path = registry_path_for_session(session_id)
    if not path.exists():
        return None
    data = load_registry_file(path)
    if not data:
        return None
    updated_at = coerce_updated_at(data.get("updated_at"), path)
    if is_stale(updated_at):
        debug(f"Registry stale for session {session_id}: {path}")
        return None
    return data


def load_registry_by_claude_pane(
    pane_id: str,
    *,
    get_backend_for_session_fn=get_backend_for_session,
) -> Optional[Dict[str, Any]]:
    if not pane_id:
        return None
    best: Optional[Dict[str, Any]] = None
    best_ts = -1
    for path in iter_registry_files():
        data = load_registry_file(path)
        if not data:
            continue
        providers = get_providers_map(data)
        claude = providers.get("claude") if isinstance(providers, dict) else None
        claude_pane = (claude or {}).get("pane_id") if isinstance(claude, dict) else None
        if (claude_pane or data.get("claude_pane_id")) != pane_id:
            continue
        updated_at = coerce_updated_at(data.get("updated_at"), path)
        if is_stale(updated_at):
            debug(f"Registry stale for pane {pane_id}: {path}")
            continue
        if updated_at > best_ts:
            best = data
            best_ts = updated_at
    return best


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

    best: Optional[Dict[str, Any]] = None
    best_ts = -1
    best_needs_migration = False

    for path in iter_registry_files():
        data = load_registry_file(path)
        if not data:
            continue
        updated_at = coerce_updated_at(data.get("updated_at"), path)
        if is_stale(updated_at):
            continue

        existing = (data.get("ccb_project_id") or "").strip()
        inferred = ""
        if not existing:
            work_dir_value = (data.get("work_dir") or "").strip()
            if work_dir_value:
                try:
                    inferred = compute_project_id_fn(Path(work_dir_value))
                except Exception:
                    inferred = ""
        effective = existing or inferred

        if effective != project_id:
            continue

        if requested_work_dir:
            record_work_dir = str(data.get("work_dir") or "").strip()
            if not path_is_same_or_parent(record_work_dir, requested_work_dir):
                continue

        if not provider_pane_alive(
            data,
            qualified_provider,
            get_backend_for_session_fn=get_backend_for_session_fn,
        ):
            continue

        if updated_at > best_ts:
            best = data
            best_ts = updated_at
            best_needs_migration = (not existing) and bool(inferred)

    if best and best_needs_migration:
        try:
            if not (best.get("ccb_project_id") or "").strip():
                work_dir_value = (best.get("work_dir") or "").strip()
                if work_dir_value:
                    best["ccb_project_id"] = compute_project_id_fn(Path(work_dir_value))
                    if upsert_registry_fn is None:
                        from .writes import upsert_registry as default_upsert_registry

                        upsert_registry_fn = default_upsert_registry
                    upsert_registry_fn(best)
        except Exception:
            pass

    return best
