from __future__ import annotations

import inspect


def ensure_project_namespace(
    project_namespace,
    *,
    layout_signature: str | None,
    recreate_namespace: bool,
    reflow_workspace: bool,
    recreate_reason: str | None,
    background_maintenance: bool,
):
    if reflow_workspace:
        return _reflow_project_workspace(
            project_namespace,
            layout_signature=layout_signature,
            recreate_reason=recreate_reason,
            background_maintenance=background_maintenance,
        )
    ensure_fn = project_namespace.ensure
    if not _namespace_kwargs_requested(
        layout_signature=layout_signature,
        recreate_namespace=recreate_namespace,
        recreate_reason=recreate_reason,
        background_maintenance=background_maintenance,
    ):
        return ensure_fn()
    kwargs = _ensure_kwargs(
        layout_signature=layout_signature,
        recreate_namespace=recreate_namespace,
        recreate_reason=recreate_reason,
        background_maintenance=background_maintenance,
    )
    try:
        signature = inspect.signature(ensure_fn)
    except (TypeError, ValueError):
        signature = None
    if signature is not None:
        kwargs = _supported_kwargs(signature, kwargs)
    if not kwargs:
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
    background_maintenance: bool,
) -> bool:
    return bool(
        recreate_namespace
        or str(recreate_reason or '').strip()
        or str(layout_signature or '').strip()
        or background_maintenance
    )


def _reflow_project_workspace(
    project_namespace,
    *,
    layout_signature: str | None,
    recreate_reason: str | None,
    background_maintenance: bool,
):
    reflow_fn = getattr(project_namespace, 'reflow_workspace', None)
    if not callable(reflow_fn):
        return ensure_project_namespace(
            project_namespace,
            layout_signature=layout_signature,
            recreate_namespace=False,
            reflow_workspace=False,
            recreate_reason=recreate_reason,
            background_maintenance=background_maintenance,
        )
    kwargs = {
        'layout_signature': layout_signature,
        'reason': recreate_reason,
        'session_probe_timeout_s': 0.0 if background_maintenance else None,
    }
    try:
        signature = inspect.signature(reflow_fn)
    except (TypeError, ValueError):
        signature = None
    if signature is not None:
        kwargs = _supported_kwargs(signature, kwargs)
    if not kwargs:
        return reflow_fn()
    try:
        return reflow_fn(**kwargs)
    except TypeError:
        return reflow_fn()


def _ensure_kwargs(
    *,
    layout_signature: str | None,
    recreate_namespace: bool,
    recreate_reason: str | None,
    background_maintenance: bool,
) -> dict[str, object]:
    return {
        'layout_signature': layout_signature,
        'force_recreate': recreate_namespace,
        'recreate_reason': recreate_reason,
        'session_probe_timeout_s': 0.0 if background_maintenance else None,
    }


def _supported_kwargs(signature: inspect.Signature, kwargs: dict[str, object]) -> dict[str, object]:
    parameters = signature.parameters
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()):
        return dict(kwargs)
    return {
        key: value
        for key, value in kwargs.items()
        if key in parameters
    }


__all__ = ['ensure_project_namespace']
