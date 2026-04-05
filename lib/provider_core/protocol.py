from __future__ import annotations

from collections.abc import Callable
import re
from dataclasses import dataclass


REQ_ID_PREFIX = "CCB_REQ_ID:"
BEGIN_PREFIX = "CCB_BEGIN:"
DONE_PREFIX = "CCB_DONE:"

LEGACY_HEX_REQ_ID_PATTERN = r"[0-9a-fA-F]{32}"
LEGACY_TIMESTAMP_REQ_ID_PATTERN = r"\d{8}-\d{6}-\d{3}-\d+-\d+"
JOB_REQ_ID_PATTERN = r"job_[a-z0-9]+"
ANY_REQ_ID_PATTERN = rf"(?:{JOB_REQ_ID_PATTERN}|{LEGACY_HEX_REQ_ID_PATTERN}|{LEGACY_TIMESTAMP_REQ_ID_PATTERN})"
REQ_ID_BOUNDARY_PATTERN = r"(?=[^A-Za-z0-9_-]|$)"

DONE_LINE_RE_TEMPLATE = r"^\s*CCB_DONE:\s*{req_id}\s*$"

_TRAILING_DONE_TAG_RE = re.compile(
    rf"^\s*(?!CCB_DONE\s*:)[A-Z][A-Z0-9_]*_DONE(?:\s*:\s*{ANY_REQ_ID_PATTERN})?\s*$"
)
ANY_DONE_LINE_RE = re.compile(rf"^\s*CCB_DONE:\s*{ANY_REQ_ID_PATTERN}\s*$", re.IGNORECASE)


def _is_trailing_noise_line(line: str) -> bool:
    if (line or "").strip() == "":
        return True
    return bool(_TRAILING_DONE_TAG_RE.match(line or ""))


def strip_trailing_markers(text: str) -> str:
    lines = [ln.rstrip("\n") for ln in (text or "").splitlines()]
    while lines:
        last = lines[-1]
        if _is_trailing_noise_line(last) or ANY_DONE_LINE_RE.match(last or ""):
            lines.pop()
            continue
        break
    return "\n".join(lines).rstrip()


_req_id_counter = 0


def make_req_id() -> str:
    global _req_id_counter
    import os
    from datetime import datetime

    now = datetime.now()
    ms = now.microsecond // 1000
    _req_id_counter += 1
    return f"{now.strftime('%Y%m%d-%H%M%S')}-{ms:03d}-{os.getpid()}-{_req_id_counter}"


def request_anchor_for_job(job_id: str | None, *, fallback_factory: Callable[[], str] | None = None) -> str:
    anchor = str(job_id or "").strip()
    if anchor:
        return anchor
    if fallback_factory is not None:
        fallback = str(fallback_factory() or "").strip()
        if fallback:
            return fallback
    raise ValueError("request anchor cannot be empty")


def wrap_codex_prompt(message: str, req_id: str) -> str:
    message = (message or "").rstrip()
    return (
        f"{REQ_ID_PREFIX} {req_id}\n\n"
        f"{message}\n\n"
        "IMPORTANT:\n"
        "- Reply normally.\n"
        "- Reply normally, in English.\n"
        "- End your reply with this exact final line (verbatim, on its own line):\n"
        f"{DONE_PREFIX} {req_id}\n"
    )


def wrap_codex_turn_prompt(message: str, req_id: str) -> str:
    message = (message or "").rstrip()
    return (
        f"{REQ_ID_PREFIX} {req_id}\n\n"
        f"{message}\n"
    )


def done_line_re(req_id: str) -> re.Pattern[str]:
    return re.compile(DONE_LINE_RE_TEMPLATE.format(req_id=re.escape(req_id)))


def is_done_text(text: str, req_id: str) -> bool:
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    for i in range(len(lines) - 1, -1, -1):
        if _is_trailing_noise_line(lines[i]):
            continue
        return bool(done_line_re(req_id).match(lines[i]))
    return False


def strip_done_text(text: str, req_id: str) -> str:
    lines = [ln.rstrip("\n") for ln in (text or "").splitlines()]
    if not lines:
        return ""

    while lines and _is_trailing_noise_line(lines[-1]):
        lines.pop()

    if lines and done_line_re(req_id).match(lines[-1] or ""):
        lines.pop()

    while lines and _is_trailing_noise_line(lines[-1]):
        lines.pop()

    return "\n".join(lines).rstrip()


def extract_reply_for_req(text: str, req_id: str) -> str:
    lines = [ln.rstrip("\n") for ln in (text or "").splitlines()]
    if not lines:
        return ""

    target_re = re.compile(rf"^\s*CCB_DONE:\s*{re.escape(req_id)}\s*$", re.IGNORECASE)
    done_idxs = [i for i, ln in enumerate(lines) if ANY_DONE_LINE_RE.match(ln or "")]
    target_idxs = [i for i in done_idxs if target_re.match(lines[i] or "")]

    if not target_idxs:
        if done_idxs:
            return ""
        return strip_done_text(text, req_id)

    target_i = target_idxs[-1]
    prev_done_i = -1
    for i in reversed(done_idxs):
        if i < target_i:
            prev_done_i = i
            break

    segment = lines[prev_done_i + 1 : target_i]

    while segment and segment[0].strip() == "":
        segment = segment[1:]
    while segment and segment[-1].strip() == "":
        segment = segment[:-1]

    return "\n".join(segment).rstrip()


@dataclass(frozen=True)
class CodexRequest:
    client_id: str
    work_dir: str
    timeout_s: float
    quiet: bool
    message: str
    req_id: str | None = None
    caller: str = "claude"


@dataclass(frozen=True)
class CodexResult:
    exit_code: int
    reply: str
    req_id: str
    session_key: str
    log_path: str | None
    anchor_seen: bool
    done_seen: bool
    fallback_scan: bool
    anchor_ms: int | None = None
    done_ms: int | None = None
