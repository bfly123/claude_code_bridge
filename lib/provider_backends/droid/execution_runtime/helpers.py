from __future__ import annotations

from pathlib import Path

from provider_core.instance_resolution import named_agent_instance
from provider_execution.common import normalize_session_path


def load_session(work_dir: Path, *, agent_name: str, primary_agent: str, load_project_session_fn):
    instance = named_agent_instance(agent_name, primary_agent=primary_agent)
    if instance is not None:
        session = load_project_session_fn(work_dir, instance)
        if session is not None:
            return session
        return None
    return load_project_session_fn(work_dir)


def state_session_path(state: dict[str, object]) -> str:
    return normalize_session_path(state.get("session_path"))


def clean_reply(
    text: str,
    *,
    req_id: str,
    is_done_text_fn,
    extract_reply_for_req_fn,
    strip_done_text_fn,
) -> str:
    if req_id and is_done_text_fn(text, req_id):
        extracted = extract_reply_for_req_fn(text, req_id)
        if extracted.strip():
            return extracted.strip()
    cleaned = strip_done_text_fn(text, req_id) if req_id else text
    return cleaned.strip() if cleaned else ""


__all__ = ["clean_reply", "load_session", "state_session_path"]
