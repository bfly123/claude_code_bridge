from __future__ import annotations

from ccbd.api_models import JobRecord
from completion.models import CompletionSourceKind
from provider_execution.active import PreparedActiveStart, prepare_active_start, resume_active_submission
from provider_execution.base import ProviderSubmission
from provider_execution.common import no_wrap_requested, preferred_session_path

from .prompt import build_exact_prompt
from .readiness import resolved_timeout
from .session import completion_dir_for_session, configure_resume_reader, state_session_path


def start_active_submission(
    adapter,
    job: JobRecord,
    *,
    context,
    now: str,
    load_session_fn,
    backend_for_session_fn,
    reader_factory,
    request_anchor_fn,
    wrap_prompt_fn,
) -> ProviderSubmission:
    prepared = prepare_active_start(
        job,
        context=context,
        provider=adapter.provider,
        source_kind=CompletionSourceKind.SESSION_SNAPSHOT,
        now=now,
        missing_session_reason='missing_gemini_session',
        load_session_fn=load_session_fn,
        backend_for_session_fn=backend_for_session_fn,
    )
    if not isinstance(prepared, PreparedActiveStart):
        return prepared

    reader = reader_factory(prepared.session)
    preferred_session = preferred_session_path(
        str(getattr(prepared.session, 'gemini_session_path', '') or ''),
        context.session_ref,
        context.session_file,
    )
    if preferred_session is not None:
        reader.set_preferred_session(preferred_session)
    state = reader.capture_state()
    session_path = state_session_path(state) or (str(preferred_session) if preferred_session is not None else '')
    request_anchor = request_anchor_fn(job.job_id)
    completion_dir = completion_dir_for_session(prepared.session)
    no_wrap = no_wrap_requested(job)
    prompt = (
        job.request.body
        if no_wrap
        else (
            build_exact_prompt(session=prepared.session, req_id=request_anchor, message=job.request.body)
            if completion_dir
            else wrap_prompt_fn(job.request.body, request_anchor)
        )
    )

    return ProviderSubmission(
        job_id=job.job_id,
        agent_name=job.agent_name,
        provider=adapter.provider,
        accepted_at=now,
        ready_at=now,
        source_kind=CompletionSourceKind.SESSION_SNAPSHOT,
        reply='',
        diagnostics={'provider': adapter.provider, 'mode': 'active', 'workspace_path': str(prepared.work_dir)},
        runtime_state={
            'mode': 'active',
            'reader': reader,
            'state': state,
            'backend': prepared.backend,
            'pane_id': prepared.pane_id,
            'request_anchor': request_anchor,
            'next_seq': 1,
            'anchor_emitted': no_wrap,
            'reply_buffer': '',
            'session_path': session_path,
            'completion_dir': completion_dir,
            'no_wrap': no_wrap,
            'prompt_text': prompt,
            'prompt_sent': False,
            'ready_wait_started_at': now,
            'ready_timeout_s': resolved_timeout(20.0),
            'ready_prompt_fingerprint': '',
            'ready_prompt_seen_at': '',
        },
    )


def resume_submission(
    job: JobRecord,
    submission: ProviderSubmission,
    *,
    context,
    load_session_fn,
    backend_for_session_fn,
    reader_factory,
) -> ProviderSubmission | None:
    return resume_active_submission(
        job,
        submission,
        context=context,
        load_session_fn=load_session_fn,
        backend_for_session_fn=backend_for_session_fn,
        reader_factory=reader_factory,
        configure_reader_fn=configure_resume_reader,
        completion_dir_fn=completion_dir_for_session,
    )


__all__ = ['resume_submission', 'start_active_submission']
