from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    coerce_updated_at,
    debug,
    get_providers_map,
    is_stale,
    iter_registry_files,
    load_registry_file,
)


def load_fresh_registry(
    path: Path,
    *,
    stale_debug_message: str | None = None,
) -> tuple[dict[str, Any], int] | None:
    if not path.exists():
        return None
    data = load_registry_file(path)
    if not data:
        return None
    updated_at = coerce_updated_at(data.get('updated_at'), path)
    if is_stale(updated_at):
        if stale_debug_message:
            debug(stale_debug_message)
        return None
    return data, updated_at


def iter_fresh_registry_records(
    *,
    work_dir: str | Path | None = None,
    stale_debug_message_fn=None,
):
    for path in iter_registry_files(work_dir=work_dir):
        stale_debug_message = stale_debug_message_fn(path) if callable(stale_debug_message_fn) else None
        record = load_fresh_registry(path, stale_debug_message=stale_debug_message)
        if record is not None:
            yield record


def latest_registry_record(records) -> tuple[dict[str, Any], int] | None:
    best: tuple[dict[str, Any], int] | None = None
    best_ts = -1
    for data, updated_at in records:
        if updated_at > best_ts:
            best = (data, updated_at)
            best_ts = updated_at
    return best


def claude_pane_id(data: dict[str, Any]) -> str | None:
    providers = get_providers_map(data)
    claude = providers.get('claude')
    if not isinstance(claude, dict):
        return None
    pane_id = str(claude.get('pane_id') or '').strip()
    return pane_id or None


__all__ = [
    'claude_pane_id',
    'iter_fresh_registry_records',
    'latest_registry_record',
    'load_fresh_registry',
]
