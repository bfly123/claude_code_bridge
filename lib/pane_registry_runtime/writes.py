from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

from cli.output import atomic_write_text
from project_id import compute_ccb_project_id

from .common import debug, get_providers_map, load_registry_file, provider_entry_from_legacy, registry_path_for_session


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
    path = registry_path_for_session(str(session_id))
    path.parent.mkdir(parents=True, exist_ok=True)

    data: Dict[str, Any] = {}
    if path.exists():
        existing = load_registry_file(path)
        if isinstance(existing, dict):
            data.update(existing)

    providers = get_providers_map(data)

    incoming_providers = record.get("providers")
    if isinstance(incoming_providers, dict):
        for provider, entry in incoming_providers.items():
            if not isinstance(provider, str) or not isinstance(entry, dict):
                continue
            key = provider.strip().lower()
            providers.setdefault(key, {})
            for entry_key, entry_value in entry.items():
                if entry_value is None:
                    continue
                providers[key][entry_key] = entry_value

    provider = record.get("provider")
    if isinstance(provider, str) and provider.strip():
        normalized_provider = provider.strip().lower()
        providers.setdefault(normalized_provider, {})
        for key, value in record.items():
            if value is None:
                continue
            if key in {"provider", "providers"}:
                continue
            if key in {"pane_id", "pane_title_marker"} or key.endswith("_session_id") or key.endswith(
                "_session_path"
            ) or key.endswith("_project_id"):
                providers[normalized_provider][key] = value

    for provider_name in ("codex", "gemini", "opencode", "claude"):
        legacy_entry = provider_entry_from_legacy(record, provider_name)
        if legacy_entry:
            providers.setdefault(provider_name, {})
            providers[provider_name].update({key: value for key, value in legacy_entry.items() if value is not None})

    for key, value in record.items():
        if value is None:
            continue
        if key in {"providers", "provider"}:
            continue
        data[key] = value

    data["providers"] = providers

    if not (data.get("ccb_project_id") or "").strip():
        work_dir = (data.get("work_dir") or "").strip()
        if work_dir:
            try:
                data["ccb_project_id"] = compute_project_id_fn(Path(work_dir))
            except Exception:
                pass

    data["updated_at"] = int(time.time())

    try:
        atomic_write_text_fn(path, json.dumps(data, ensure_ascii=False, indent=2))
        return True
    except Exception as exc:
        debug(f"Failed to write registry {path}: {exc}")
        return False
