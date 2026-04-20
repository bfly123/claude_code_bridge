from __future__ import annotations

from pathlib import Path
from typing import Callable

from ccbd.api_models import JobRecord
from completion.models import CompletionSourceKind

from ..base import ProviderRuntimeContext, ProviderSubmission
from ..common import error_submission
from .models import PreparedActiveStart


def _session_selector_name(job: JobRecord) -> str:
    if getattr(job, 'provider_instance', None):
        return str(job.provider_instance)
    if str(job.agent_name or '').strip():
        return str(job.agent_name)
    return str(job.provider)


def prepare_active_start(
    job: JobRecord,
    *,
    context: ProviderRuntimeContext | None,
    provider: str,
    source_kind: CompletionSourceKind,
    now: str,
    missing_session_reason: str,
    load_session_fn: Callable[[Path, str], object | None],
    backend_for_session_fn: Callable[[dict], object | None],
) -> ProviderSubmission | PreparedActiveStart:
    if context is None or not context.workspace_path:
        return error_submission(
            job,
            provider=provider,
            now=now,
            source_kind=source_kind,
            reason="runtime_unavailable",
            error="missing_runtime_context",
        )

    work_dir = Path(context.workspace_path).expanduser()
    session = load_session_fn(work_dir, agent_name=_session_selector_name(job))
    if session is None:
        return error_submission(
            job,
            provider=provider,
            now=now,
            source_kind=source_kind,
            reason="runtime_unavailable",
            error=missing_session_reason,
        )

    ok, pane_or_err = session.ensure_pane()
    if not ok:
        return error_submission(
            job,
            provider=provider,
            now=now,
            source_kind=source_kind,
            reason="pane_unavailable",
            error=str(pane_or_err),
        )

    backend = backend_for_session_fn(session.data)
    if backend is None:
        return error_submission(
            job,
            provider=provider,
            now=now,
            source_kind=source_kind,
            reason="backend_unavailable",
            error="terminal backend not available",
        )

    return PreparedActiveStart(
        work_dir=work_dir,
        session=session,
        pane_id=str(pane_or_err),
        backend=backend,
    )


__all__ = ["prepare_active_start"]
