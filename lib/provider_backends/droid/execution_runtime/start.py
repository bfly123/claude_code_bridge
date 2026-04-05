from __future__ import annotations

from pathlib import Path

from ccbd.api_models import JobRecord
from completion.models import CompletionSourceKind
from provider_execution.active import PreparedActiveStart, prepare_active_start
from provider_execution.base import ProviderRuntimeContext, ProviderSubmission
from provider_execution.common import preferred_session_path, send_prompt_to_runtime_target


def start_submission(
    job: JobRecord,
    *,
    context: ProviderRuntimeContext | None,
    now: str,
    provider: str,
    load_session_fn,
    backend_for_session_fn,
    reader_cls,
    request_anchor_fn,
    wrap_prompt_fn,
) -> ProviderSubmission:
    prepared = prepare_active_start(
        job,
        context=context,
        provider=provider,
        source_kind=CompletionSourceKind.TERMINAL_TEXT,
        now=now,
        missing_session_reason="missing_droid_session",
        load_session_fn=load_session_fn,
        backend_for_session_fn=backend_for_session_fn,
    )
    if not isinstance(prepared, PreparedActiveStart):
        return prepared

    reader = reader_cls(work_dir=Path(prepared.session.work_dir))
    preferred = preferred_session_path(str(getattr(prepared.session, "droid_session_path", "") or ""), context.session_ref)
    if preferred is not None:
        reader.set_preferred_session(preferred)
    session_id = str(getattr(prepared.session, "droid_session_id", "") or "").strip()
    if session_id:
        reader.set_session_id_hint(session_id)
    state = reader.capture_state()
    request_anchor = request_anchor_fn(job.job_id)
    send_prompt_to_runtime_target(prepared.backend, prepared.pane_id, wrap_prompt_fn(job.request.body, request_anchor))

    return ProviderSubmission(
        job_id=job.job_id,
        agent_name=job.agent_name,
        provider=provider,
        accepted_at=now,
        ready_at=now,
        source_kind=CompletionSourceKind.TERMINAL_TEXT,
        reply="",
        diagnostics={"provider": provider, "mode": "active", "workspace_path": str(prepared.work_dir)},
        runtime_state={
            "mode": "active",
            "reader": reader,
            "state": state,
            "backend": prepared.backend,
            "pane_id": prepared.pane_id,
            "request_anchor": request_anchor,
            "next_seq": 1,
            "anchor_seen": False,
            "reply_buffer": "",
            "raw_buffer": "",
            "session_path": state_session_path(state),
        },
    )


def state_session_path(state: dict[str, object]) -> str:
    from .helpers import state_session_path as _state_session_path

    return _state_session_path(state)


__all__ = ["start_submission"]
