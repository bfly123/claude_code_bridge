from __future__ import annotations

from .ensure_context import load_namespace_context
from .ensure_identity import prepare_namespace_root_pane
from .ensure_state import (
    build_created_namespace,
    force_recreate_namespace,
    persist_refreshed_namespace,
    recreate_for_layout_change,
)


def ensure_project_namespace(
    controller,
    *,
    layout_signature: str | None = None,
    force_recreate: bool = False,
    recreate_reason: str | None = None,
) -> object:
    controller._layout.ccbd_dir.mkdir(parents=True, exist_ok=True)
    context = load_namespace_context(
        controller,
        layout_signature=layout_signature,
        recreate_reason=recreate_reason,
    )

    if force_recreate:
        context = force_recreate_namespace(controller, context)
    context = recreate_for_layout_change(controller, context)

    if context.session_is_alive and context.current is not None:
        return persist_refreshed_namespace(controller, context)

    prepare_namespace_root_pane(
        controller,
        context,
        epoch=context.current.namespace_epoch + 1 if context.current is not None else 1,
    )
    return build_created_namespace(controller, context)


__all__ = ['ensure_project_namespace']
