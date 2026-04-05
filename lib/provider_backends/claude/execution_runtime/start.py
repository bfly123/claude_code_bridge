from __future__ import annotations

import os
import re
import time
from pathlib import Path

from ccbd.api_models import JobRecord
from completion.models import CompletionSourceKind
from provider_core.instance_resolution import named_agent_instance
from provider_execution.active import PreparedActiveStart, prepare_active_start, resume_active_submission
from provider_execution.base import ProviderRuntimeContext, ProviderSubmission
from provider_execution.common import preferred_session_path, send_prompt_to_runtime_target

from ..protocol import wrap_claude_prompt, wrap_claude_turn_prompt
from provider_hooks.artifacts import completion_dir_from_session_data


def load_session(load_project_session_fn, work_dir: Path, *, agent_name: str):
    instance = named_agent_instance(agent_name, primary_agent="claude")
    if instance is not None:
        session = load_project_session_fn(work_dir, instance)
        if session is not None:
            return session
        return None
    return load_project_session_fn(work_dir)


def provider_preferred_session_path(*, session, context: ProviderRuntimeContext) -> Path | None:
    return preferred_session_path(str(getattr(session, "claude_session_path", "") or ""), context.session_ref)


def configure_resume_reader(reader, state: dict[str, object], context: ProviderRuntimeContext) -> None:
    preferred_session = preferred_session_path(str(state.get("session_path") or ""), context.session_ref)
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


def looks_ready(text: str) -> bool:
    normalized = str(text or "")
    lowered = normalized.lower()
    if "type your message" in lowered or "esc to interrupt" in lowered:
        return True
    if "for shortcuts" in lowered and _has_prompt_line(normalized):
        return True
    return _has_prompt_line(normalized) and not _looks_like_banner_only(lowered)


_PROMPT_LINE_RE = re.compile(r"(^|\n)\s*❯(?:\s|\n|$)")


def _has_prompt_line(text: str) -> bool:
    return bool(_PROMPT_LINE_RE.search(str(text or "")))


def _looks_like_banner_only(lowered: str) -> bool:
    text = str(lowered or "")
    if "welcome back!" not in text:
        return False
    return "for shortcuts" not in text and "esc to interrupt" not in text and "type your message" not in text


def wait_for_runtime_ready(backend: object, pane_id: str, *, timeout_s: float = 8.0) -> None:
    get_pane_content = getattr(backend, "get_pane_content", None)
    if not callable(get_pane_content):
        return
    try:
        timeout_s = max(0.0, float(os.environ.get("CCB_CLAUDE_READY_TIMEOUT_S", timeout_s)))
    except Exception:
        timeout_s = max(0.0, timeout_s)
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
    request_anchor = request_anchor_fn(job.job_id)
    completion_dir = completion_dir_for_session(prepared.session)
    wait_for_runtime_ready(prepared.backend, prepared.pane_id)
    provider_options = dict(getattr(job, "provider_options", {}) or {})
    no_wrap = bool(provider_options.get("no_wrap"))
    prompt = (
        job.request.body
        if no_wrap
        else (
            wrap_claude_turn_prompt(job.request.body, request_anchor)
            if completion_dir
            else wrap_claude_prompt(job.request.body, request_anchor)
        )
    )
    send_prompt(prepared.backend, prepared.pane_id, prompt)

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
            "anchor_seen": False,
            "reply_buffer": "",
            "raw_buffer": "",
            "session_path": state_session_path(state),
            "completion_dir": completion_dir,
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
