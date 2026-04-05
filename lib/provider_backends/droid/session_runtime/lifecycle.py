from __future__ import annotations

from provider_backends.pane_log_support.lifecycle import attach_pane_log as _attach_pane_log_impl
from provider_backends.pane_log_support.lifecycle import ensure_pane as _ensure_pane_impl
from .pathing import now_str


def attach_pane_log(session, backend: object, pane_id: str) -> None:
    _attach_pane_log_impl(session, backend, pane_id)


def ensure_pane(session) -> tuple[bool, str]:
    return _ensure_pane_impl(session, now_str_fn=now_str, attach_pane_log_fn=attach_pane_log)


__all__ = ["attach_pane_log", "ensure_pane"]
