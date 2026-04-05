from __future__ import annotations

import os
import re
from pathlib import Path

from env_utils import env_bool
from provider_core.protocol import (
    ANY_DONE_LINE_RE,
    BEGIN_PREFIX,
    DONE_PREFIX,
    REQ_ID_PREFIX,
    is_done_text,
    make_req_id,
    strip_done_text,
)
_SKILL_CACHE: str | None = None


def _wants_markdown_table(message: str) -> bool:
    msg = (message or "").lower()
    if "markdown" not in msg:
        return False
    return ("table" in msg) or ("\u8868\u683c" in message)

def _language_hint() -> str:
    lang = (os.environ.get("CCB_REPLY_LANG") or os.environ.get("CCB_LANG") or "").strip().lower()
    if lang in {"zh", "cn", "chinese"}:
        return "Reply in Chinese."
    if lang in {"en", "english"}:
        return "Reply in English."
    return ""


def _load_claude_skills() -> str:
    global _SKILL_CACHE
    if _SKILL_CACHE is not None:
        return _SKILL_CACHE
    if not env_bool("CCB_CLAUDE_SKILLS", True):
        _SKILL_CACHE = ""
        return _SKILL_CACHE
    skills_dir = Path(__file__).resolve().parents[2] / "claude_skills"
    if not skills_dir.is_dir():
        _SKILL_CACHE = ""
        return _SKILL_CACHE
    parts: list[str] = []
    # Load short skill files (aligned with droid)
    for name in ("ask.md",):
        path = skills_dir / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if text:
            parts.append(text)
    _SKILL_CACHE = "\n\n".join(parts).strip()
    return _SKILL_CACHE


def extract_reply_for_req(text: str, req_id: str) -> str:
    """
    Extract the reply segment for req_id from a Claude message.

    Claude sometimes emits multiple replies in a single assistant message, each ending with its own
    `CCB_DONE: <req_id>` line. In that case, we want only the segment between the previous done line
    (any req_id) and the done line for our req_id.
    """
    lines = [ln.rstrip("\n") for ln in (text or "").splitlines()]
    if not lines:
        return ""

    # Find last done-line index for this req_id (may not be last line if the model misbehaves).
    target_re = re.compile(rf"^\s*CCB_DONE:\s*{re.escape(req_id)}\s*$", re.IGNORECASE)
    begin_re = re.compile(rf"^\s*{re.escape(BEGIN_PREFIX)}\s*{re.escape(req_id)}\s*$", re.IGNORECASE)
    done_idxs = [i for i, ln in enumerate(lines) if ANY_DONE_LINE_RE.match(ln or "")]
    target_idxs = [i for i in done_idxs if target_re.match(lines[i] or "")]

    if not target_idxs:
        # Fallback: keep existing behavior (strip only if the last line matches).
        return strip_done_text(text, req_id)

    target_i = target_idxs[-1]
    begin_i = None
    for i in range(target_i - 1, -1, -1):
        if begin_re.match(lines[i] or ""):
            begin_i = i
            break

    if begin_i is not None:
        segment = lines[begin_i + 1 : target_i]
    else:
        prev_done_i = -1
        for i in reversed(done_idxs):
            if i < target_i:
                prev_done_i = i
                break
        segment = lines[prev_done_i + 1 : target_i]
    # Trim leading/trailing blank lines for nicer output.
    while segment and segment[0].strip() == "":
        segment = segment[1:]
    while segment and segment[-1].strip() == "":
        segment = segment[:-1]
    return "\n".join(segment).rstrip()


def wrap_claude_prompt(message: str, req_id: str) -> str:
    message = (message or "").rstrip()
    skills = _load_claude_skills()
    if skills:
        message = f"{skills}\n\n{message}".strip()
    extra_lines: list[str] = []
    if _wants_markdown_table(message):
        extra_lines.append("If asked for a Markdown table, output only pipe-and-dash Markdown table syntax (no box-drawing characters).")
    lang_hint = _language_hint()
    if lang_hint:
        extra_lines.append(lang_hint)
    extra = "\n".join(extra_lines).strip()
    if extra:
        extra = f"{extra}\n\n"
    return (
        f"{REQ_ID_PREFIX} {req_id}\n\n"
        f"{message}\n\n"
        f"{extra}"
        "Reply using exactly this format:\n"
        f"{BEGIN_PREFIX} {req_id}\n"
        "<reply>\n"
        f"{DONE_PREFIX} {req_id}\n"
    )


def wrap_claude_turn_prompt(message: str, req_id: str) -> str:
    message = (message or "").rstrip()
    skills = _load_claude_skills()
    if skills:
        message = f"{skills}\n\n{message}".strip()
    extra_lines: list[str] = []
    if _wants_markdown_table(message):
        extra_lines.append("If asked for a Markdown table, output only pipe-and-dash Markdown table syntax (no box-drawing characters).")
    lang_hint = _language_hint()
    if lang_hint:
        extra_lines.append(lang_hint)
    extra = "\n".join(extra_lines).strip()
    if extra:
        extra = f"{extra}\n\n"
    return (
        f"{REQ_ID_PREFIX} {req_id}\n\n"
        f"{message}\n\n"
        f"{extra}"
    )
__all__ = [
    "wrap_claude_prompt",
    "wrap_claude_turn_prompt",
    "extract_reply_for_req",
    "make_req_id",
    "is_done_text",
    "strip_done_text",
]
