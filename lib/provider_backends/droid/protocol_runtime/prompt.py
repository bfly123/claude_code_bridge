from __future__ import annotations

from provider_core.protocol import DONE_PREFIX, REQ_ID_PREFIX

from .skills import load_droid_skills


def wrap_droid_prompt(message: str, req_id: str) -> str:
    body = _with_skills((message or "").rstrip())
    return (
        f"{REQ_ID_PREFIX} {req_id}\n\n"
        f"{body}\n\n"
        "IMPORTANT:\n"
        "- Reply with an execution summary, in English. Do not stay silent.\n"
        "- End your reply with this exact final line (verbatim, on its own line):\n"
        f"{DONE_PREFIX} {req_id}\n"
    )


def _with_skills(message: str) -> str:
    skills = load_droid_skills()
    if not skills:
        return message
    return f"{skills}\n\n{message}".strip()


__all__ = ["wrap_droid_prompt"]
