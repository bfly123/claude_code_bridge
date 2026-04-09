from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable

from ccbd.api_models import JobRecord
from completion.models import CompletionSourceKind
from provider_core.instance_resolution import named_agent_instance
from provider_execution.active import PreparedActiveStart, prepare_active_start
from provider_execution.base import ProviderRuntimeContext, ProviderSubmission
from provider_execution.common import no_wrap_requested, normalize_session_path, send_prompt_to_runtime_target


def start_active_submission(
    adapter,
    job: JobRecord,
    *,
    context: ProviderRuntimeContext | None,
    now: str,
    load_session_fn: Callable[[Path, str], object | None],
    backend_for_session_fn: Callable[[dict], object | None],
    reader_factory: Callable[[object, Path | None], object],
    request_anchor_fn: Callable[[str | None], str],
    wrap_prompt_fn: Callable[[str, str], str],
) -> ProviderSubmission:
    prepared = prepare_active_start(
        job,
        context=context,
        provider=adapter.provider,
        source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM,
        now=now,
        missing_session_reason='missing_codex_session',
        load_session_fn=load_session_fn,
        backend_for_session_fn=backend_for_session_fn,
    )
    if not isinstance(prepared, PreparedActiveStart):
        return prepared

    reader = reader_factory(prepared.session, None)
    state = reader.capture_state()
    request_anchor = request_anchor_fn(job.job_id)
    no_wrap = no_wrap_requested(job)
    prompt = job.request.body if no_wrap else wrap_prompt_fn(job.request.body, request_anchor)
    send_prompt_to_runtime_target(prepared.backend, prepared.pane_id, prompt)

    return ProviderSubmission(
        job_id=job.job_id,
        agent_name=job.agent_name,
        provider=adapter.provider,
        accepted_at=now,
        ready_at=now,
        source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM,
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
            'anchor_seen': no_wrap,
            'bound_turn_id': '',
            'bound_task_id': '',
            'reply_buffer': '',
            'last_agent_message': '',
            'last_final_answer': '',
            'last_assistant_message': '',
            'last_assistant_signature': '',
            'session_path': state_session_path(state),
            'no_wrap': no_wrap,
        },
    )


def resume_submission(
    job: JobRecord,
    submission: ProviderSubmission,
    *,
    context: ProviderRuntimeContext | None,
    load_session_fn: Callable[[Path, str], object | None],
    backend_for_session_fn: Callable[[dict], object | None],
    reader_factory: Callable[[object, Path | None], object],
) -> ProviderSubmission | None:
    if context is None or not context.workspace_path:
        return None
    state = dict(submission.runtime_state)
    if str(state.get('mode') or 'passive') != 'active':
        return None
    work_dir = Path(context.workspace_path).expanduser()
    session = load_session_fn(work_dir, job.agent_name)
    if session is None:
        return None
    ok, pane_or_err = session.ensure_pane()
    if not ok:
        return None
    backend = backend_for_session_fn(session.data)
    if backend is None:
        return None
    preferred_log = preferred_log_path(state)
    reader = reader_factory(session, preferred_log)
    return replace(
        submission,
        runtime_state={
            **state,
            'reader': reader,
            'backend': backend,
            'pane_id': str(pane_or_err),
            'mode': 'active',
            'session_path': state.get('session_path') or (str(preferred_log) if preferred_log else ''),
        },
    )


def load_session(load_project_session_fn, work_dir: Path, *, agent_name: str):
    instance = named_agent_instance(agent_name, primary_agent='codex')
    if instance is not None:
        session = load_project_session_fn(work_dir, instance)
        if session is not None:
            return session
        return None
    return load_project_session_fn(work_dir)


def preferred_log_path(state: dict[str, object]) -> Path | None:
    raw = state.get('session_path') or state_session_path(state.get('state') or {})
    session_path = normalize_session_path(raw)
    if not session_path:
        return None
    try:
        return Path(session_path).expanduser()
    except Exception:
        return None


def state_session_path(state: dict[str, object]) -> str:
    return normalize_session_path(state.get('log_path'))


__all__ = [
    'load_session',
    'preferred_log_path',
    'resume_submission',
    'start_active_submission',
    'state_session_path',
]
