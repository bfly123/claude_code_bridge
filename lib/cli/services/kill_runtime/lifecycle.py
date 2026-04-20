from __future__ import annotations


def destroy_project_namespace(
    context,
    *,
    force: bool,
    project_namespace_controller_cls,
    start_policy_store_cls,
) -> None:
    project_namespace_controller_cls(context.paths, context.project.project_id).destroy(
        reason='kill',
        force=force,
    )
    try:
        start_policy_store_cls(context.paths).clear()
    except Exception:
        pass


__all__ = ['destroy_project_namespace']
