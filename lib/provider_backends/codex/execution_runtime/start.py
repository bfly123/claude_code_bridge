from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable

from ccbd.api_models import JobRecord
from completion.models import CompletionSourceKind
from provider_core.instance_resolution import named_agent_instance
from provider_execution.active_runtime.start import load_runtime_session
from provider_execution.active import PreparedActiveStart, prepare_active_start
from provider_execution.base import ProviderRuntimeContext, ProviderSubmission
from provider_execution.common import no_wrap_requested, normalize_session_path, preferred_session_path, send_prompt_to_runtime_target

from ..session_runtime.model import CodexProjectSession
from ..session_runtime.pathing import read_json


def start_active_submission(
    adapter,
    job: JobRecord,
    *,
    context: ProviderRuntimeContext | None,
    now: str,
    load_session_fn: Callable[[Path, str], object | None],
    backend_for_session_fn: Callable[[dict], object | None],
    reader_factory: Callable[[object, Path | None, str | None], object],
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

    preferred_log = preferred_log_path(
        {},
        session_path=getattr(prepared.session, 'codex_session_path', '') or '',
        context=context,
    )
    preferred_session_id = preferred_runtime_session_id(context)
    reader = reader_factory(prepared.session, preferred_log, preferred_session_id)
    state = reader.capture_state()
    session_path = state_session_path(state) or (str(preferred_log) if preferred_log is not None else '')
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
            'session_path': session_path,
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
    reader_factory: Callable[[object, Path | None, str | None], object],
) -> ProviderSubmission | None:
    if context is None or not context.workspace_path:
        return None
    state = dict(submission.runtime_state)
    if str(state.get('mode') or 'passive') != 'active':
        return None
    work_dir = Path(context.workspace_path).expanduser()
    session = load_runtime_session(
        load_session_fn=load_session_fn,
        work_dir=work_dir,
        agent_name=job.agent_name,
        context=context,
    )
    if session is None:
        return None
    ok, pane_or_err = session.ensure_pane()
    if not ok:
        return None
    backend = backend_for_session_fn(session.data)
    if backend is None:
        return None
    preferred_log = preferred_log_path(
        state,
        session_path=getattr(session, 'codex_session_path', '') or '',
        context=context,
    )
    reader = reader_factory(session, preferred_log, preferred_runtime_session_id(context))
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


def load_session(
    load_project_session_fn,
    work_dir: Path,
    *,
    agent_name: str,
    session_file: str | None = None,
    session_id: str | None = None,
    session_ref: str | None = None,
):
    del session_id
    instance = named_agent_instance(agent_name, primary_agent='codex')
    if instance is not None:
        session = load_project_session_fn(work_dir, instance)
        if session is not None:
            return session
    else:
        session = load_project_session_fn(work_dir)
        if session is not None:
            return session
    preferred = preferred_session_path('', session_ref, session_file)
    if preferred is None or not preferred.is_file():
        return None
    data = read_json(preferred)
    if not data:
        return None
    return CodexProjectSession(session_file=preferred, data=data)


def preferred_log_path(
    state: dict[str, object],
    *,
    session_path: object = None,
    context: ProviderRuntimeContext | None = None,
) -> Path | None:
    preferred = preferred_session_path(
        state.get('session_path') or state_session_path(state.get('state') or {}) or session_path,
        context.session_ref if context is not None else None,
        context.session_file if context is not None else None,
    )
    if preferred is not None:
        return preferred
    raw = state.get('session_path') or state_session_path(state.get('state') or {})
    session_path = normalize_session_path(raw)
    if not session_path:
        return None
    try:
        return Path(session_path).expanduser()
    except Exception:
        return None


def preferred_runtime_session_id(context: ProviderRuntimeContext | None) -> str | None:
    text = str(getattr(context, 'session_id', '') or '').strip()
    return text or None


def state_session_path(state: dict[str, object]) -> str:
    return normalize_session_path(state.get('log_path'))


__all__ = [
    'load_session',
    'preferred_log_path',
    'resume_submission',
    'start_active_submission',
    'state_session_path',
]
