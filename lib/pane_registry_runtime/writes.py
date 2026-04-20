from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

from cli.output import atomic_write_text
from project.identity import compute_ccb_project_id
from project.runtime_paths import project_anchor_exists

from .common import debug, get_providers_map, load_registry_file, registry_path_for_session


def upsert_registry(
    record: Dict[str, Any],
    *,
    atomic_write_text_fn=atomic_write_text,
    compute_project_id_fn=compute_ccb_project_id,
) -> bool:
    session_id = record.get("ccb_session_id")
    if not session_id:
        debug("Registry update skipped: missing ccb_session_id")
        return False
    work_dir = str(record.get("work_dir") or "").strip()
    if not work_dir:
        debug("Registry update skipped: missing work_dir for project-scoped registry")
        return False
    if not project_anchor_exists(Path(work_dir)):
        debug(f"Registry update skipped: no .ccb anchor for {work_dir}")
        return False
    path = registry_path_for_session(str(session_id), work_dir=Path(work_dir))
    path.parent.mkdir(parents=True, exist_ok=True)

    data: Dict[str, Any] = {}
    if path.exists():
        existing = load_registry_file(path)
        if isinstance(existing, dict):
            data.update(existing)

    providers = get_providers_map(data)
    _merge_provider_maps(providers, record)
    _merge_top_level_fields(data, record)

    data["providers"] = providers
    _ensure_project_id(data, compute_project_id_fn=compute_project_id_fn)
    data["updated_at"] = int(time.time())

    try:
        atomic_write_text_fn(path, json.dumps(data, ensure_ascii=False, indent=2))
        return True
    except Exception as exc:
        debug(f"Failed to write registry {path}: {exc}")
        return False


def _merge_provider_maps(providers: Dict[str, Any], record: Dict[str, Any]) -> None:
    incoming_providers = record.get("providers")
    if isinstance(incoming_providers, dict):
        for provider, entry in incoming_providers.items():
            if not isinstance(provider, str) or not isinstance(entry, dict):
                continue
            _merge_provider_entry(providers, provider.strip().lower(), entry)

    provider = record.get("provider")
    if isinstance(provider, str) and provider.strip():
        normalized = provider.strip().lower()
        providers.setdefault(normalized, {})
        for key, value in _single_provider_fields(record).items():
            providers[normalized][key] = value


def _merge_provider_entry(providers: Dict[str, Any], provider: str, entry: dict) -> None:
    providers.setdefault(provider, {})
    for entry_key, entry_value in entry.items():
        if entry_value is not None:
            providers[provider][entry_key] = entry_value


def _single_provider_fields(record: Dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key, value in record.items():
        if value is None or key in {"provider", "providers"}:
            continue
        if _provider_field(key):
            fields[key] = value
    return fields


def _provider_field(key: str) -> bool:
    return (
        key in {"pane_id", "pane_title_marker"}
        or key.endswith("_session_id")
        or key.endswith("_session_path")
        or key.endswith("_project_id")
    )


def _merge_top_level_fields(data: Dict[str, Any], record: Dict[str, Any]) -> None:
    for key, value in record.items():
        if value is not None and key not in {"providers", "provider"}:
            data[key] = value


def _ensure_project_id(data: Dict[str, Any], *, compute_project_id_fn) -> None:
    if (data.get("ccb_project_id") or "").strip():
        return
    work_dir = (data.get("work_dir") or "").strip()
    if not work_dir:
        return
    try:
        data["ccb_project_id"] = compute_project_id_fn(Path(work_dir))
    except Exception:
        return
