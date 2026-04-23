from __future__ import annotations

import os
import time
from pathlib import Path

from ccbd.api_models import JobRecord
from completion.models import CompletionSourceKind
from provider_core.instance_resolution import named_agent_instance
from provider_execution.active import PreparedActiveStart, prepare_active_start, resume_active_submission
from provider_execution.base import ProviderRuntimeContext, ProviderSubmission
from provider_execution.common import no_wrap_requested, preferred_session_path, send_prompt_to_runtime_target

from ..protocol import wrap_claude_prompt, wrap_claude_turn_prompt
from provider_hooks.artifacts import completion_dir_from_session_data


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
    instance = named_agent_instance(agent_name, primary_agent="claude")
    if instance is not None:
        session = load_project_session_fn(work_dir, instance)
        if session is not None:
            return session
    else:
        session = load_project_session_fn(work_dir)
        if session is not None:
            return session
    preferred = preferred_session_path('', session_ref, session_file)
    if preferred is None:
        return None
    from ..session_runtime.loading import _load_session_from_file

    return _load_session_from_file(preferred, fallback_work_dir=work_dir)


def provider_preferred_session_path(*, session, context: ProviderRuntimeContext) -> Path | None:
    return preferred_session_path(
        str(getattr(session, "claude_session_path", "") or ""),
        context.session_ref,
        context.session_file,
    )


def configure_resume_reader(reader, state: dict[str, object], context: ProviderRuntimeContext) -> None:
    preferred_session = preferred_session_path(
        str(state.get("session_path") or ""),
        context.session_ref,
        context.session_file,
    )
    if preferred_session is not None:
        reader.set_preferred_session(preferred_session)


def completion_dir_for_session(session) -> str:
    path = completion_dir_from_session_data(dict(getattr(session, "data", {}) or {}))
    return str(path) if path is not None else ""


def state_session_path(state: dict[str, object]) -> str:
    from provider_execution.common import normalize_session_path

    return normalize_session_path(state.get("session_path"))


def send_prompt(backend: object, pane_id: str, text: str) -> None:
    send_prompt_to_runtime_target(backend, pane_id, text)


def resolved_ready_timeout(timeout_s: float = 8.0) -> float:
    try:
        return max(0.0, float(os.environ.get("CCB_CLAUDE_READY_TIMEOUT_S", timeout_s)))
    except Exception:
        return max(0.0, timeout_s)


def looks_ready(text: str) -> bool:
    normalized = str(text or "")
    lowered = normalized.lower()
    if _has_prompt_line(normalized):
        return True
    if "type your message" in lowered or "esc to interrupt" in lowered:
        return True
    if "for shortcuts" in lowered:
        return True
    return False


def _has_prompt_line(text: str) -> bool:
    for line in str(text or "").splitlines():
        stripped = line.lstrip()
        if not stripped.startswith("❯"):
            continue
        tail = stripped[1:]
        if not tail or tail.isspace():
            return True
    return False

def wait_for_runtime_ready(backend: object, pane_id: str, *, timeout_s: float = 8.0) -> None:
    get_pane_content = getattr(backend, "get_pane_content", None)
    if not callable(get_pane_content):
        return
    timeout_s = resolved_ready_timeout(timeout_s)
    deadline = time.time() + timeout_s
    saw_content = False
    while time.time() < deadline:
        try:
            text = str(get_pane_content(pane_id, lines=120) or "")
        except Exception:
            return
        if text.strip():
            saw_content = True
        if looks_ready(text):
            return
        time.sleep(0.2)
    if saw_content:
        return


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
) -> ProviderSubmission:
    prepared = prepare_active_start(
        job,
        context=context,
        provider=adapter.provider,
        source_kind=CompletionSourceKind.SESSION_EVENT_LOG,
        now=now,
        missing_session_reason="missing_claude_session",
        load_session_fn=load_session_fn,
        backend_for_session_fn=backend_for_session_fn,
    )
    if not isinstance(prepared, PreparedActiveStart):
        return prepared

    reader = reader_factory(prepared.session)
    preferred_session = provider_preferred_session_path(session=prepared.session, context=context)
    if preferred_session is not None:
        reader.set_preferred_session(preferred_session)
    state = reader.capture_state()
    session_path = state_session_path(state) or (str(preferred_session) if preferred_session is not None else '')
    request_anchor = request_anchor_fn(job.job_id)
    completion_dir = completion_dir_for_session(prepared.session)
    no_wrap = no_wrap_requested(job)
    reply_delivery = str(job.request.message_type or "").strip().lower() == "reply_delivery"
    prompt = (
        job.request.body
        if no_wrap
        else (
            wrap_claude_turn_prompt(job.request.body, request_anchor)
            if completion_dir
            else wrap_claude_prompt(job.request.body, request_anchor)
        )
    )

    return ProviderSubmission(
        job_id=job.job_id,
        agent_name=job.agent_name,
        provider=adapter.provider,
        accepted_at=now,
        ready_at=now,
        source_kind=CompletionSourceKind.SESSION_EVENT_LOG,
        reply="",
        diagnostics={"provider": adapter.provider, "mode": "active", "workspace_path": str(prepared.work_dir)},
        runtime_state={
            "mode": "active",
            "reader": reader,
            "state": state,
            "backend": prepared.backend,
            "pane_id": prepared.pane_id,
            "request_anchor": request_anchor,
            "next_seq": 1,
            "anchor_seen": no_wrap,
            "reply_buffer": "",
            "raw_buffer": "",
            "session_path": session_path,
            "completion_dir": completion_dir,
            "no_wrap": no_wrap,
            "prompt_text": prompt,
            "prompt_sent": False,
            "reply_delivery_complete_on_dispatch": reply_delivery,
            "reply_delivery_require_ready": reply_delivery,
            "ready_wait_started_at": now,
            "ready_timeout_s": resolved_ready_timeout(),
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
