from __future__ import annotations

import inspect


def ensure_project_namespace(
    project_namespace,
    *,
    layout_signature: str | None,
    recreate_namespace: bool,
    recreate_reason: str | None,
):
    ensure_fn = project_namespace.ensure
    if not _namespace_kwargs_requested(
        layout_signature=layout_signature,
        recreate_namespace=recreate_namespace,
        recreate_reason=recreate_reason,
    ):
        return ensure_fn()
    kwargs = _ensure_kwargs(
        layout_signature=layout_signature,
        recreate_namespace=recreate_namespace,
        recreate_reason=recreate_reason,
    )
    try:
        signature = inspect.signature(ensure_fn)
    except (TypeError, ValueError):
        signature = None
    if signature is not None and not _supports_namespace_kwargs(signature):
        return ensure_fn()
    try:
        return ensure_fn(**kwargs)
    except TypeError:
        return ensure_fn()


def _namespace_kwargs_requested(
    *,
    layout_signature: str | None,
    recreate_namespace: bool,
    recreate_reason: str | None,
) -> bool:
    return bool(
        recreate_namespace
        or str(recreate_reason or '').strip()
        or str(layout_signature or '').strip()
    )


def _ensure_kwargs(
    *,
    layout_signature: str | None,
    recreate_namespace: bool,
    recreate_reason: str | None,
) -> dict[str, object]:
    return {
        'layout_signature': layout_signature,
        'force_recreate': recreate_namespace,
        'recreate_reason': recreate_reason,
    }


def _supports_namespace_kwargs(signature: inspect.Signature) -> bool:
    parameters = signature.parameters
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()):
        return True
    supported = {'layout_signature', 'force_recreate', 'recreate_reason'}
    return supported <= set(parameters)


__all__ = ['ensure_project_namespace']
