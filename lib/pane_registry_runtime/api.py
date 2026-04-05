from __future__ import annotations

from cli.output import atomic_write_text
from project_id import compute_ccb_project_id
from terminal_runtime import get_backend_for_session

from .lookup import (
    load_registry_by_claude_pane as _load_registry_by_claude_pane_impl,
    load_registry_by_project_id as _load_registry_by_project_id_impl,
    load_registry_by_session_id as _load_registry_by_session_id_impl,
)
from .writes import upsert_registry as _upsert_registry_impl


def load_registry_by_session_id(session_id: str):
    return _load_registry_by_session_id_impl(session_id)


def load_registry_by_claude_pane(pane_id: str):
    return _load_registry_by_claude_pane_impl(
        pane_id,
        get_backend_for_session_fn=get_backend_for_session,
    )


def load_registry_by_project_id(ccb_project_id: str, provider: str, *, work_dir=None):
    return _load_registry_by_project_id_impl(
        ccb_project_id,
        provider,
        work_dir=work_dir,
        get_backend_for_session_fn=get_backend_for_session,
        compute_project_id_fn=compute_ccb_project_id,
        upsert_registry_fn=upsert_registry,
    )


def upsert_registry(record):
    return _upsert_registry_impl(
        record,
        atomic_write_text_fn=atomic_write_text,
        compute_project_id_fn=compute_ccb_project_id,
    )


__all__ = [
    "load_registry_by_claude_pane",
    "load_registry_by_project_id",
    "load_registry_by_session_id",
    "upsert_registry",
]
