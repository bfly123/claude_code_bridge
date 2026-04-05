from __future__ import annotations

import os
import time
from pathlib import Path

from ccbd.api_models import JobRecord
from completion.models import CompletionSourceKind
from provider_core.instance_resolution import named_agent_instance
from provider_execution.active import PreparedActiveStart, prepare_active_start, resume_active_submission
from provider_execution.base import ProviderRuntimeContext, ProviderSubmission
from provider_execution.common import normalize_session_path, preferred_session_path, send_prompt_to_runtime_target
from provider_hooks.artifacts import completion_dir_from_session_data


def load_session(load_project_session_fn, work_dir: Path, *, agent_name: str):
    instance = named_agent_instance(agent_name, primary_agent='gemini')
    if instance is not None:
        session = load_project_session_fn(work_dir, instance)
        if session is not None:
            return session
        return None
    return load_project_session_fn(work_dir)


def state_session_path(state: dict[str, object]) -> str:
    return normalize_session_path(state.get('session_path'))


def completion_dir_for_session(session) -> str:
    path = completion_dir_from_session_data(dict(getattr(session, 'data', {}) or {}))
    return str(path) if path is not None else ''


def configure_resume_reader(reader, state: dict[str, object], context: ProviderRuntimeContext) -> None:
    preferred_session = preferred_session_path(
        str(state.get('session_path') or ''),
        context.session_ref,
    )
    if preferred_session is not None:
        reader.set_preferred_session(preferred_session)


def send_prompt(backend: object, pane_id: str, text: str) -> None:
    send_prompt_to_runtime_target(backend, pane_id, text)


def looks_ready(text: str) -> bool:
    return 'Type your message' in str(text or '')


def wait_for_runtime_ready(backend: object, pane_id: str, *, timeout_s: float = 20.0) -> None:
    get_pane_content = getattr(backend, 'get_pane_content', None)
    if not callable(get_pane_content):
        return
    try:
        timeout_s = max(0.0, float(os.environ.get('CCB_GEMINI_READY_TIMEOUT_S', timeout_s)))
    except Exception:
        timeout_s = max(0.0, timeout_s)
    deadline = time.time() + timeout_s
    stable_text = ''
    stable_since: float | None = None
    saw_content = False
    while time.time() < deadline:
        try:
            text = str(get_pane_content(pane_id, lines=120) or '')
        except Exception:
            return
        if text.strip():
            saw_content = True
        if looks_ready(text):
            fingerprint = text.strip()
            if fingerprint == stable_text:
                if stable_since is None:
                    stable_since = time.time()
                elif time.time() - stable_since >= 1.5:
                    time.sleep(0.3)
                    return
            else:
                stable_text = fingerprint
                stable_since = time.time()
        else:
            stable_text = ''
            stable_since = None
        time.sleep(0.2)
    if saw_content:
        return


def write_request_file(*, session, req_id: str, message: str) -> Path:
    work_dir_root = str(getattr(session, 'work_dir', '') or '') or str(getattr(session, 'runtime_dir', '') or '') or '.'
    work_dir = Path(work_dir_root).expanduser()
    request_dir = work_dir / '.ccb-requests'
    request_dir.mkdir(parents=True, exist_ok=True)
    request_path = request_dir / f'{req_id}.md'
    request_path.write_text(str(message or ''), encoding='utf-8')
    return request_path


def build_exact_prompt(*, session, req_id: str, message: str) -> str:
    request_path = write_request_file(session=session, req_id=req_id, message=message)
    return f'CCB_REQ_ID: {req_id} Execute the full request from @{request_path} and reply directly.'


def start_active_submission(
    adapter,
    job: JobRecord,
    *,
    context: ProviderRuntimeContext | None,
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
    )
    if preferred_session is not None:
        reader.set_preferred_session(preferred_session)
    state = reader.capture_state()
    request_anchor = request_anchor_fn(job.job_id)
    completion_dir = completion_dir_for_session(prepared.session)
    wait_for_runtime_ready(prepared.backend, prepared.pane_id)
    prompt = (
        build_exact_prompt(session=prepared.session, req_id=request_anchor, message=job.request.body)
        if completion_dir
        else wrap_prompt_fn(job.request.body, request_anchor)
    )
    send_prompt(prepared.backend, prepared.pane_id, prompt)

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
            'anchor_emitted': False,
            'reply_buffer': '',
            'session_path': state_session_path(state),
            'completion_dir': completion_dir,
        },
    )


def resume_submission(
    job: JobRecord,
    submission: ProviderSubmission,
    *,
    context: ProviderRuntimeContext | None,
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


__all__ = [
    'build_exact_prompt',
    'completion_dir_for_session',
    'configure_resume_reader',
    'load_session',
    'looks_ready',
    'resume_submission',
    'send_prompt',
    'start_active_submission',
    'state_session_path',
    'wait_for_runtime_ready',
    'write_request_file',
]
