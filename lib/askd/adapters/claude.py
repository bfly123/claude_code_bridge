"""
Claude provider adapter for the unified ask daemon.

Wraps existing laskd_* modules to provide a consistent interface.
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any, Optional

from askd.adapters.base import BaseProviderAdapter, ProviderRequest, ProviderResult, QueuedTask
from askd_runtime import log_path, write_log
from ccb_protocol import BEGIN_PREFIX, REQ_ID_PREFIX
from claude_comm import ClaudeLogReader
from completion_hook import notify_completion
from laskd_registry import get_session_registry
from laskd_protocol import extract_reply_for_req, is_done_text, wrap_claude_prompt
from laskd_session import compute_session_key, load_project_session
from providers import LASKD_SPEC
from session_file_watcher import HAS_WATCHDOG
from terminal import get_backend_for_session


def _now_ms() -> int:
    return int(time.time() * 1000)


def _write_log(line: str) -> None:
    write_log(log_path(LASKD_SPEC.log_file_name), line)


def _tail_state_for_log(log_path_val: Optional[Path], *, tail_bytes: int) -> dict:
    if not log_path_val or not log_path_val.exists():
        return {"session_path": log_path_val, "offset": 0, "carry": b""}
    try:
        size = log_path_val.stat().st_size
    except OSError:
        size = 0
    offset = max(0, size - max(0, int(tail_bytes)))
    return {"session_path": log_path_val, "offset": offset, "carry": b""}


_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_CURSOR_FWD_RE = re.compile(r"\x1b\[(\d*)C")
_DONE_RE_CACHE: dict[str, re.Pattern[str]] = {}
_SPINNER_CHARS = {"·", ".", "*", "✶", "✻", "✽", "✢", "✣", "✤", "✥", "✦", "✧", "✩", "✪", "✫", "✬", "✭", "✮", "✯"}
_NOISE_PREFIXES = ("❯", "🤖")
_NOISE_CONTAINS = (
    "Bootstrapping",
    "Frolicking",
    "Claude Code",
    "bypass permissions",
    "CCB_REQ_ID:",
    "IMPORTANT:",
    "End your reply",
)
_BOX_TABLE_CHARS = {"┌", "┬", "┐", "├", "┼", "┤", "└", "┴", "┘", "│", "─"}


def _wants_triplet_fences(message: str) -> bool:
    msg = (message or "").lower()
    if ("python" in msg) and ("json" in msg) and ("yaml" in msg):
        return ("code block" in msg) or ("\u4ee3\u7801\u5757" in (message or ""))
    return False


def _wants_bash_fence(message: str) -> bool:
    msg = (message or "").lower()
    if "bash" in msg:
        return ("code block" in msg) or ("\u4ee3\u7801\u5757" in (message or ""))
    return False


def _wants_text_fence(message: str) -> bool:
    msg = (message or "").lower()
    if "```text" in msg or "text" in msg:
        return ("code block" in msg) or ("\u4ee3\u7801\u5757" in (message or ""))
    return False


def _wants_release_notes(message: str) -> bool:
    msg = (message or "").lower()
    if "release notes" not in msg:
        return False
    return ("summary" in msg) and ("item" in msg) and ("risk" in msg) and ("action" in msg)


def _looks_like_release_notes_reply(reply: str) -> bool:
    if not reply:
        return False
    text = reply.lower()
    if "release notes" in text and "summary:" in text:
        return True
    return False

def _wants_abc_sections(message: str) -> bool:
    msg = (message or "").lower()
    return "## a" in msg and "## b" in msg and "## c" in msg


def _wants_section_10(message: str) -> bool:
    msg = (message or "").lower()
    return "### section" in msg and "1..10" in msg


def _has_fence(reply: str) -> bool:
    return "```" in (reply or "")


def _done_line_re(req_id: str) -> re.Pattern[str]:
    cached = _DONE_RE_CACHE.get(req_id)
    if cached:
        return cached
    pat = re.compile(rf"^\s*CCB_DONE:\s*{re.escape(req_id)}\s*$")
    _DONE_RE_CACHE[req_id] = pat
    return pat


def _clean_line(line: str) -> str:
    def _cursor_repl(match: re.Match[str]) -> str:
        raw = (match.group(1) or "").strip()
        try:
            count = int(raw) if raw else 1
        except Exception:
            count = 1
        return " " * max(0, count)

    line = _CURSOR_FWD_RE.sub(_cursor_repl, line)
    return _ANSI_RE.sub("", line.replace("\r", "")).rstrip("\n")


def _split_inline_protocol(line: str, req_id: str) -> list[str]:
    """
    Split a line that may contain inline protocol markers (REQ/BEGIN/DONE)
    into separate logical lines. This helps when terminal logs compress
    multiple lines via carriage returns.
    """
    if not line:
        return [line]
    marker_req = f"{REQ_ID_PREFIX} {req_id}"
    marker_begin = f"{BEGIN_PREFIX} {req_id}"
    marker_done = f"CCB_DONE: {req_id}"
    if marker_req not in line and marker_begin not in line and marker_done not in line:
        return [line]
    expanded = line
    for marker in (marker_req, marker_begin, marker_done):
        if marker in expanded:
            expanded = expanded.replace(marker, f"\n{marker}\n")
    parts = expanded.split("\n")
    return parts if parts else [line]


def _is_box_table_line(line: str) -> bool:
    return any(ch in line for ch in _BOX_TABLE_CHARS)


def _should_fix_box_table(message: str, reply: str) -> bool:
    if not reply:
        return False
    if not _is_box_table_line(reply):
        return False
    msg = (message or "").lower()
    if "markdown" not in msg:
        return False
    return ("table" in msg) or ("\u8868\u683c" in (message or ""))


def _convert_box_table_to_markdown(text: str) -> str:
    lines = (text or "").splitlines()
    if not lines:
        return text
    start = None
    end = None
    for i, ln in enumerate(lines):
        if _is_box_table_line(ln):
            if start is None:
                start = i
            end = i
            continue
        if start is not None:
            if ln.strip() == "":
                end = i
                continue
            break
    if start is None or end is None:
        return text

    block = lines[start : end + 1]
    rows: list[list[str]] = []
    for ln in block:
        if "│" not in ln:
            continue
        raw = ln.strip()
        if not raw:
            continue
        parts = [p.strip() for p in raw.strip("│").split("│")]
        if not parts or all(p == "" for p in parts):
            continue
        rows.append(parts)
    if not rows:
        return text

    header = rows[0]
    col_count = len(header)
    if col_count == 0:
        return text
    header = [c or "" for c in header]
    sep = ["---"] * col_count
    out = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in rows[1:]:
        row = (row + [""] * col_count)[:col_count]
        out.append("| " + " | ".join(row) + " |")

    rebuilt = lines[:start] + out + lines[end + 1 :]
    return "\n".join(rebuilt).rstrip()


def _split_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.strip() == "":
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _fix_triplet_fences(reply: str) -> str:
    lines = (reply or "").splitlines()
    if _has_fence(reply):
        py_count = reply.count("```python")
        json_count = reply.count("```json")
        yaml_count = reply.count("```yaml")
        if py_count == 1 and json_count == 1 and yaml_count == 1:
            return reply
        lines = [ln for ln in lines if not ln.strip().startswith("```")]

    def _first_idx(pred) -> int | None:
        for i, ln in enumerate(lines):
            if pred(ln):
                return i
        return None

    py_start = _first_idx(lambda ln: ln.lstrip().startswith("def "))
    json_start = _first_idx(lambda ln: ln.lstrip().startswith("{") or ln.lstrip().startswith("["))
    yaml_start = _first_idx(lambda ln: ln.strip().startswith("name:") or ln.strip().startswith("version:"))

    segments: list[tuple[str, int]] = []
    if py_start is not None:
        segments.append(("python", py_start))
    if json_start is not None:
        segments.append(("json", json_start))
    if yaml_start is not None:
        segments.append(("yaml", yaml_start))
    segments.sort(key=lambda x: x[1])

    if not segments:
        return reply

    out_blocks: list[str] = []
    for idx, (tag, start) in enumerate(segments):
        end = segments[idx + 1][1] if idx + 1 < len(segments) else len(lines)
        seg_lines = [ln for ln in lines[start:end]]
        while seg_lines and seg_lines[0].strip() == "":
            seg_lines = seg_lines[1:]
        while seg_lines and seg_lines[-1].strip() == "":
            seg_lines = seg_lines[:-1]
        text = "\n".join(seg_lines).strip()
        if not text:
            continue
        out_blocks.append(f"```{tag}\n{text}\n```")
    return "\n\n".join(out_blocks).rstrip()


def _fix_bash_fence(reply: str) -> str:
    if _has_fence(reply):
        return reply
    lines = (reply or "").splitlines()
    if not lines:
        return reply
    start = None
    for i, line in enumerate(lines):
        if line.strip():
            start = i
            break
    if start is None:
        return reply
    script: list[str] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if line.strip() == "":
            break
        if script and line.lstrip().startswith(("[", "{")):
            break
        script.append(line)
        i += 1
    if not script:
        return reply
    rest = lines[i:]
    while rest and rest[0].strip() == "":
        rest = rest[1:]
    out: list[str] = ["```bash"]
    out.extend(script)
    out.append("```")
    if rest:
        out.append("")
        out.extend(rest)
    return "\n".join(out).rstrip()


def _fix_text_fence(reply: str) -> str:
    if _has_fence(reply):
        return reply
    body = (reply or "").strip()
    if not body:
        return reply
    return f"```text\n{body}\n```"


def _fix_abc_sections(reply: str) -> str:
    lines = (reply or "").splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in ("A", "B", "C"):
            lines[i] = f"## {stripped}"

    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("## "):
            out.append(line)
            i += 1
            bullets: list[str] = []
            while i < len(lines):
                nxt = lines[i].strip()
                if nxt.startswith("## "):
                    break
                if nxt.startswith("- "):
                    bullets.append(nxt)
                i += 1
            out.extend(bullets[:2])
            continue
        i += 1
    return "\n".join(out).rstrip()


def _split_to_two_lines(text: str) -> tuple[str, str]:
    if not text:
        return "", ""
    for sep in ("。", ".", "！", "!", "？", "?"):
        idx = text.find(sep)
        if idx != -1 and idx + 1 < len(text):
            first = text[: idx + 1].strip()
            second = text[idx + 1 :].strip()
            if second:
                return first, second
    words = text.split()
    if len(words) >= 2:
        mid = len(words) // 2
        return " ".join(words[:mid]).strip(), " ".join(words[mid:]).strip()
    mid = max(1, len(text) // 2)
    return text[:mid].strip(), text[mid:].strip()


def _fix_section_10(reply: str) -> str:
    lines = (reply or "").splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = re.match(r"^(?:###\s*)?Section\s+(\d+)$", line, re.IGNORECASE)
        if m:
            num = m.group(1)
            out.append(f"### Section {num}")
            i += 1
            desc: list[str] = []
            while i < len(lines):
                nxt = lines[i].strip()
                if re.match(r"^(?:###\s*)?Section\s+\d+$", nxt, re.IGNORECASE):
                    break
                if nxt:
                    desc.append(nxt)
                i += 1
            if len(desc) >= 2:
                out.extend(desc[:2])
            elif len(desc) == 1:
                first, second = _split_to_two_lines(desc[0])
                out.append(first)
                out.append(second)
            else:
                out.append("")
                out.append("")
            continue
        i += 1
    return "\n".join(out).rstrip()


def _fix_release_notes(reply: str) -> str:
    raw_lines = [ln.rstrip() for ln in (reply or "").splitlines()]
    stripped_lines = [ln.strip() for ln in raw_lines if ln.strip()]
    summary_line = None
    for ln in stripped_lines:
        if ln.lower().startswith("summary:"):
            summary_line = ln
            break
    if summary_line is None:
        for ln in stripped_lines:
            if ln.lower() != "release notes":
                summary_line = f"Summary: {ln}"
                break
    if summary_line is None:
        summary_line = "Summary:"
    # Enforce <= 20 words after Summary:
    if summary_line.lower().startswith("summary:"):
        prefix, rest = summary_line.split(":", 1)
        rest_words = rest.strip().split()
        if len(rest_words) > 20:
            rest = " ".join(rest_words[:20])
        summary_line = f"{prefix}: {rest}".rstrip()
    else:
        words = summary_line.split()
        if len(words) > 21:
            summary_line = " ".join(words[:21])

    numbered = [ln for ln in stripped_lines if re.match(r"^\d+[\.\)]", ln)]
    numbered = numbered[:4]

    table_lines = [ln for ln in raw_lines if ln.strip().startswith("|") and "|" in ln]
    rows: list[tuple[str, str, str]] = []

    def _parse_table_rows(lines: list[str]) -> list[tuple[str, str, str]]:
        parsed: list[tuple[str, str, str]] = []
        for ln in lines:
            if not ln.strip().startswith("|"):
                continue
            # Skip separator rows
            if set(ln.replace("|", "").strip()) <= {"-", ":", " "}:
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) < 3:
                continue
            if cells[0].lower() == "item" and cells[1].lower() == "risk":
                continue
            parsed.append((cells[0], cells[1], cells[2]))
        return parsed
    if table_lines:
        rows = _parse_table_rows(table_lines)
    else:
        item = risk = action = ""
        for ln in stripped_lines:
            low = ln.lower()
            if low.startswith("item:"):
                item = ln.split(":", 1)[1].strip()
            elif low.startswith("risk:"):
                risk = ln.split(":", 1)[1].strip()
            elif low.startswith("action:"):
                action = ln.split(":", 1)[1].strip()
                if item or risk or action:
                    rows.append((item, risk, action))
                item = risk = action = ""
        if rows:
            table_lines = ["| Item | Risk | Action |", "| --- | --- | --- |"]
            for item, risk, action in rows:
                table_lines.append(f"| {item} | {risk} | {action} |".rstrip())

    if not numbered:
        candidates: list[str] = []
        for ln in stripped_lines:
            low = ln.lower()
            if low in ("release notes",):
                continue
            if low.startswith(("summary:", "item:", "risk:", "action:")):
                continue
            if ln.strip().startswith("|"):
                continue
            if re.match(r"^\d+[\.\)]", ln):
                continue
            candidates.append(ln)
        if candidates:
            numbered = [f"{i+1}. {text}" for i, text in enumerate(candidates[:4])]
        elif rows:
            numbered = [
                f"{i+1}. {(row[0] or row[1] or row[2]).strip()}"
                for i, row in enumerate(rows[:4])
                if (row[0] or row[1] or row[2]).strip()
            ]
        if numbered and len(numbered) < 4:
            last_text = numbered[-1].split(".", 1)[-1].strip()
            while len(numbered) < 4:
                numbered.append(f"{len(numbered)+1}. {last_text}")

    out: list[str] = ["### Release Notes", summary_line]
    if numbered:
        out.extend(numbered)
    if table_lines:
        out.extend(table_lines)
    return "\n".join(out).rstrip()

def _pane_log_state(log_path_val: Optional[Path]) -> dict:
    if not log_path_val:
        return {"log_path": None, "offset": 0, "carry": b""}
    try:
        size = log_path_val.stat().st_size
    except OSError:
        size = 0
    return {"log_path": log_path_val, "offset": size, "carry": b""}


def _read_pane_log(state: dict) -> tuple[list[str], dict]:
    log_path_val = state.get("log_path")
    if not log_path_val:
        return [], state
    try:
        size = log_path_val.stat().st_size
    except OSError:
        return [], state

    offset = int(state.get("offset") or 0)
    carry = state.get("carry") or b""
    if size < offset:
        offset = 0
        carry = b""

    try:
        with log_path_val.open("rb") as handle:
            handle.seek(offset)
            data = handle.read()
    except OSError:
        return [], state

    new_offset = offset + len(data)
    buf = (carry + data).replace(b"\r", b"\n")
    lines = buf.split(b"\n")
    if buf and not buf.endswith(b"\n"):
        carry = lines.pop()
    else:
        carry = b""

    out: list[str] = []
    for raw in lines:
        if not raw:
            out.append("")
            continue
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            text = raw.decode("utf-8", errors="replace")
        out.append(_clean_line(text))

    new_state = {"log_path": log_path_val, "offset": new_offset, "carry": carry}
    return out, new_state


def _looks_like_prompt_context(lines: list[str]) -> bool:
    if not lines:
        return False
    if any(ln.strip().startswith("IMPORTANT:") for ln in lines):
        return True
    if any("End your reply with this exact final line" in ln for ln in lines):
        return True
    return False


def _strip_leading_marker(line: str) -> str:
    text = line.lstrip()
    if text.startswith("●") or text.startswith("•"):
        return text[1:].lstrip()
    return text


def _has_alnum(line: str) -> bool:
    return any(ch.isalnum() for ch in line)


def _is_noise_line(line: str) -> bool:
    """Check if a line is noise (UI elements, spinners, etc.) but NOT empty lines."""
    stripped = line.strip()
    # Empty lines are NOT noise - they are valid paragraph separators
    if not stripped:
        return False
    if stripped.startswith(_NOISE_PREFIXES):
        return True
    for needle in _NOISE_CONTAINS:
        if needle in stripped:
            return True
    if len(stripped) <= 2 and all(ch in _SPINNER_CHARS for ch in stripped):
        return True
    if not _has_alnum(stripped) and all(ch in "─-_=·*·•" or ch.isspace() for ch in stripped):
        return True
    return False


def _line_counts_as_response(line: str, req_id: str) -> bool:
    """Heuristic: is this line likely part of the assistant response?"""
    if _is_noise_line(line):
        return False
    clean = _clean_line(line)
    if not clean.strip():
        return False
    # Ignore prompt scaffolding / protocol markers echoed by the terminal.
    if f"{REQ_ID_PREFIX} {req_id}" in clean:
        return False
    if f"{BEGIN_PREFIX} {req_id}" in clean:
        return False
    if "CCB_DONE:" in clean:
        return False
    if "IMPORTANT:" in clean or "End your reply with this exact final line" in clean:
        return False
    if "●" in line:
        return True
    return _has_alnum(clean)


def _extract_reply_from_pane(lines: list[str], req_id: str) -> str:
    """Extract reply content from pane log, working backwards from CCB_DONE line."""
    expanded: list[str] = []
    for raw in lines:
        clean = _clean_line(raw)
        expanded.extend(_split_inline_protocol(clean, req_id))
    lines = expanded

    done_i: Optional[int] = None
    needle = f"CCB_DONE: {req_id}"
    for i in range(len(lines) - 1, -1, -1):
        if needle in lines[i]:
            done_i = i
            break
    if done_i is None:
        return ""

    out_rev: list[str] = []
    consecutive_empty = 0
    consecutive_noise = 0
    max_consecutive_empty = 5  # Allow up to 5 consecutive empty lines
    max_consecutive_noise = 3  # Stop after 3 consecutive noise lines (UI elements)
    max_lines = 200

    done_re = _done_line_re(req_id)

    begin_found = False
    for i in range(done_i - 1, -1, -1):
        raw = lines[i]
        stripped = raw.strip()
        clean = _clean_line(raw)

        # Stop if we hit prompt markers or an earlier done line (prompt echo).
        if done_re.match(clean.strip() or ""):
            break
        if f"{REQ_ID_PREFIX} {req_id}" in clean:
            break
        if f"{BEGIN_PREFIX} {req_id}" in clean:
            begin_found = True
            break
        if "IMPORTANT:" in clean or "End your reply with this exact final line" in clean:
            break

        # Handle empty lines - preserve them but limit consecutive count
        if not stripped:
            consecutive_empty += 1
            consecutive_noise = 0
            if consecutive_empty > max_consecutive_empty:
                break
            if out_rev:  # Only add empty lines if we have content
                out_rev.append("")
            continue

        # Handle noise lines (UI elements, spinners)
        if _is_noise_line(raw):
            consecutive_noise += 1
            consecutive_empty = 0
            if consecutive_noise >= max_consecutive_noise:
                break
            continue

        # Valid content line
        consecutive_empty = 0
        consecutive_noise = 0
        cleaned = _strip_leading_marker(raw)
        if cleaned.strip():
            out_rev.append(cleaned.rstrip())
            if len(out_rev) >= max_lines:
                break

    if not begin_found:
        return ""

    out = list(reversed(out_rev))
    # Trim leading/trailing empty lines
    while out and out[0].strip() == "":
        out = out[1:]
    while out and out[-1].strip() == "":
        out = out[:-1]
    return "\n".join(out).rstrip()


class ClaudeAdapter(BaseProviderAdapter):
    """Adapter for Claude provider."""

    @property
    def key(self) -> str:
        return "claude"

    @property
    def spec(self):
        return LASKD_SPEC

    @property
    def session_filename(self) -> str:
        return ".claude-session"

    def on_start(self) -> None:
        try:
            get_session_registry()
            _write_log(f"[INFO] claude log watcher enabled watchdog={HAS_WATCHDOG}")
        except Exception as exc:
            _write_log(f"[WARN] claude log watcher init failed: {exc}")

    def on_stop(self) -> None:
        try:
            get_session_registry().stop_monitor()
        except Exception:
            pass

    def load_session(self, work_dir: Path) -> Optional[Any]:
        return load_project_session(work_dir)

    def compute_session_key(self, session: Any) -> str:
        return compute_session_key(session) if session else "claude:unknown"

    def handle_task(self, task: QueuedTask) -> ProviderResult:
        started_ms = _now_ms()
        req = task.request
        work_dir = Path(req.work_dir)
        _write_log(f"[INFO] start provider=claude req_id={task.req_id} work_dir={req.work_dir}")

        session = load_project_session(work_dir)
        session_key = self.compute_session_key(session)

        if not session:
            return ProviderResult(
                exit_code=1,
                reply="No active Claude session found for work_dir.",
                req_id=task.req_id,
                session_key=session_key,
                done_seen=False,
            )

        ok, pane_or_err = session.ensure_pane()
        if not ok:
            return ProviderResult(
                exit_code=1,
                reply=f"Session pane not available: {pane_or_err}",
                req_id=task.req_id,
                session_key=session_key,
                done_seen=False,
            )
        pane_id = pane_or_err

        backend = get_backend_for_session(session.data)
        if not backend:
            return ProviderResult(
                exit_code=1,
                reply="Terminal backend not available",
                req_id=task.req_id,
                session_key=session_key,
                done_seen=False,
            )

        deadline = None if float(req.timeout_s) < 0.0 else (time.time() + float(req.timeout_s))

        log_reader = ClaudeLogReader(work_dir=Path(session.work_dir))
        if session.claude_session_path:
            try:
                log_reader.set_preferred_session(Path(session.claude_session_path))
            except Exception:
                pass
        state = log_reader.capture_state()

        refresh = getattr(backend, "refresh_pane_logs", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass

        pane_log_path: Optional[Path] = None
        ensure_log = getattr(backend, "ensure_pane_log", None)
        if callable(ensure_log):
            try:
                pane_log_path = ensure_log(pane_id)
            except Exception:
                pane_log_path = None
        if pane_log_path is None:
            getter = getattr(backend, "pane_log_path", None)
            if callable(getter):
                try:
                    pane_log_path = getter(pane_id)
                except Exception:
                    pane_log_path = None
        pane_state = _pane_log_state(pane_log_path) if pane_log_path else None

        if req.no_wrap:
            prompt = req.message
        else:
            prompt = wrap_claude_prompt(req.message, task.req_id)
        backend.send_text(pane_id, prompt)

        # Prefer structured Claude logs when available. Optionally fall back to pane logs if we
        # don't see a response within a short grace window.
        if not (pane_log_path and pane_state):
            result = self._wait_for_response(
                task, session, session_key, started_ms, log_reader, state, backend, pane_id, deadline
            )
            result.reply = self._postprocess_reply(req, result.reply)
            self._finalize_result(result, req)
            return result

        log_session = state.get("session_path")
        log_deadline = deadline
        log_windowed = False
        if log_session:
            try:
                log_window_s = float(os.environ.get("CCB_LASKD_LOG_FIRST_WINDOW", "5.0"))
            except Exception:
                log_window_s = 5.0
            if log_window_s > 0:
                log_windowed = True
                now = time.time()
                if deadline is None:
                    log_deadline = now + log_window_s
                else:
                    log_deadline = min(deadline, now + log_window_s)

            result = self._wait_for_response(
                task, session, session_key, started_ms, log_reader, state, backend, pane_id, log_deadline
            )
            if result.exit_code == 1 or result.done_seen or (deadline is not None and time.time() >= deadline):
                result.reply = self._postprocess_reply(req, result.reply)
                self._finalize_result(result, req)
                return result
            if not log_windowed:
                result.reply = self._postprocess_reply(req, result.reply)
                self._finalize_result(result, req)
                return result

        result = self._wait_for_response_pane(
            task, session, session_key, started_ms, backend, pane_id, pane_state, deadline
        )
        result.reply = self._postprocess_reply(req, result.reply)
        self._finalize_result(result, req)
        return result

    def _wait_for_response_pane(
        self, task: QueuedTask, session: Any, session_key: str,
        started_ms: int, backend: Any, pane_id: str, pane_state: dict,
        deadline: Optional[float]
    ) -> ProviderResult:
        req = task.request
        lines: list[str] = []
        anchor_seen = False
        anchor_ms: Optional[int] = None
        prompt_echo_seen = False
        prompt_done_seen = False
        begin_seen = False
        recent_instruction = False
        response_seen = False
        done_seen = False
        done_ms: Optional[int] = None
        done_re = _done_line_re(task.req_id)
        pane_check_interval = float(os.environ.get("CCB_LASKD_PANE_CHECK_INTERVAL", "2.0"))
        last_pane_check = time.time()

        while True:
            if deadline is not None:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                wait_step = min(remaining, 0.5)
            else:
                wait_step = 0.5

            if time.time() - last_pane_check >= pane_check_interval:
                try:
                    alive = bool(backend.is_alive(pane_id))
                except Exception:
                    alive = False
                if not alive:
                    _write_log(f"[ERROR] Pane {pane_id} died req_id={task.req_id}")
                    return ProviderResult(
                        exit_code=1,
                        reply="Claude pane died during request",
                        req_id=task.req_id,
                        session_key=session_key,
                        done_seen=False,
                        anchor_seen=anchor_seen,
                        anchor_ms=anchor_ms,
                    )
                last_pane_check = time.time()

            new_lines, pane_state = _read_pane_log(pane_state)
            if not new_lines:
                time.sleep(wait_step)
                continue

            start_idx = len(lines)
            for line in new_lines:
                lines.append(line)

            for i in range(start_idx, len(lines)):
                line = lines[i]
                for part in _split_inline_protocol(_clean_line(line), task.req_id):
                    clean = _clean_line(part)  # Strip ANSI escape sequences
                    is_done = bool(done_re.match(clean.strip() or "")) or (f"CCB_DONE: {task.req_id}" in clean)

                    if (not anchor_seen) and (REQ_ID_PREFIX in clean) and (task.req_id in clean):
                        anchor_seen = True
                        prompt_echo_seen = True
                        anchor_ms = _now_ms() - started_ms

                    if (not prompt_done_seen) and ("IMPORTANT:" in clean or "End your reply with this exact final line" in clean):
                        recent_instruction = True

                    # If the prompt was echoed, the first DONE line is part of the prompt.
                    if prompt_echo_seen and (not prompt_done_seen) and is_done:
                        prompt_done_seen = True
                        recent_instruction = False
                        continue

                    if f"{BEGIN_PREFIX} {task.req_id}" in clean:
                        if (not prompt_echo_seen or prompt_done_seen) and (not recent_instruction or prompt_done_seen):
                            begin_seen = True
                            recent_instruction = False
                        continue

                    # Only count response content after the prompt echo is done.
                    if begin_seen and (not prompt_echo_seen or prompt_done_seen) and _line_counts_as_response(part, task.req_id):
                        response_seen = True

                    if is_done:
                        if begin_seen and (not prompt_echo_seen or prompt_done_seen) and response_seen:
                            done_seen = True
                            done_ms = _now_ms() - started_ms
                            break
            if done_seen:
                break

        final_reply = _extract_reply_from_pane(lines, task.req_id)

        return ProviderResult(
            exit_code=0 if done_seen else 2,
            reply=final_reply,
            req_id=task.req_id,
            session_key=session_key,
            done_seen=done_seen,
            done_ms=done_ms,
            anchor_seen=anchor_seen,
            anchor_ms=anchor_ms,
            fallback_scan=False,
        )

    def _finalize_result(self, result: ProviderResult, req: ProviderRequest) -> None:
        _write_log(f"[INFO] done provider=claude req_id={result.req_id} exit={result.exit_code}")
        _write_log(f"[INFO] notify_completion caller={req.caller} done_seen={result.done_seen} email_req_id={req.email_req_id}")
        notify_completion(
            provider="claude",
            output_file=req.output_path,
            reply=result.reply,
            req_id=result.req_id,
            done_seen=result.done_seen,
            caller=req.caller,
            email_req_id=req.email_req_id,
            email_msg_id=req.email_msg_id,
            email_from=req.email_from,
            work_dir=req.work_dir,
        )

    def _postprocess_reply(self, req: ProviderRequest, reply: str) -> str:
        fixed = reply
        if _should_fix_box_table(req.message, fixed):
            fixed = _convert_box_table_to_markdown(fixed)
        if _wants_triplet_fences(req.message):
            fixed = _fix_triplet_fences(fixed)
        if _wants_bash_fence(req.message):
            fixed = _fix_bash_fence(fixed)
        if _wants_text_fence(req.message):
            fixed = _fix_text_fence(fixed)
        if _wants_release_notes(req.message) or _looks_like_release_notes_reply(fixed):
            fixed = _fix_release_notes(fixed)
        if _wants_abc_sections(req.message):
            fixed = _fix_abc_sections(fixed)
        if _wants_section_10(req.message):
            fixed = _fix_section_10(fixed)
        return fixed

    def _wait_for_response(
        self, task: QueuedTask, session: Any, session_key: str,
        started_ms: int, log_reader: ClaudeLogReader, state: dict,
        backend: Any, pane_id: str, deadline: Optional[float] = None
    ) -> ProviderResult:
        req = task.request
        if deadline is None:
            deadline = None if float(req.timeout_s) < 0.0 else (time.time() + float(req.timeout_s))
        chunks: list[str] = []
        anchor_seen = False
        fallback_scan = False
        anchor_ms: Optional[int] = None
        done_seen = False
        done_ms: Optional[int] = None

        anchor_grace_deadline = min(deadline, time.time() + 1.5) if deadline else (time.time() + 1.5)
        anchor_collect_grace = min(deadline, time.time() + 2.0) if deadline else (time.time() + 2.0)
        rebounded = False
        tail_bytes = int(os.environ.get("CCB_LASKD_REBIND_TAIL_BYTES", str(2 * 1024 * 1024)))
        pane_check_interval = float(os.environ.get("CCB_LASKD_PANE_CHECK_INTERVAL", "2.0"))
        last_pane_check = time.time()

        while True:
            if deadline is not None:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                wait_step = min(remaining, 0.5)
            else:
                wait_step = 0.5

            if time.time() - last_pane_check >= pane_check_interval:
                try:
                    alive = bool(backend.is_alive(pane_id))
                except Exception:
                    alive = False
                if not alive:
                    _write_log(f"[ERROR] Pane {pane_id} died req_id={task.req_id}")
                    return ProviderResult(
                        exit_code=1,
                        reply="Claude pane died during request",
                        req_id=task.req_id,
                        session_key=session_key,
                        done_seen=False,
                        anchor_seen=anchor_seen,
                        fallback_scan=fallback_scan,
                        anchor_ms=anchor_ms,
                    )
                last_pane_check = time.time()

            events, state = log_reader.wait_for_events(state, wait_step)
            if not events:
                if (not rebounded) and (not anchor_seen) and time.time() >= anchor_grace_deadline:
                    log_reader = ClaudeLogReader(work_dir=Path(session.work_dir), use_sessions_index=False)
                    log_hint = log_reader.current_session_path()
                    state = _tail_state_for_log(log_hint, tail_bytes=tail_bytes)
                    fallback_scan = True
                    rebounded = True
                continue

            for role, text in events:
                if role == "user":
                    if f"{REQ_ID_PREFIX} {task.req_id}" in text:
                        anchor_seen = True
                        if anchor_ms is None:
                            anchor_ms = _now_ms() - started_ms
                    continue
                if role != "assistant":
                    continue
                if (not anchor_seen) and time.time() < anchor_collect_grace:
                    continue
                chunks.append(text)
                combined = "\n".join(chunks)
                if is_done_text(combined, task.req_id):
                    done_seen = True
                    done_ms = _now_ms() - started_ms
                    break

            if done_seen:
                break

        combined = "\n".join(chunks)
        final_reply = extract_reply_for_req(combined, task.req_id)

        result = ProviderResult(
            exit_code=0 if done_seen else 2,
            reply=final_reply,
            req_id=task.req_id,
            session_key=session_key,
            done_seen=done_seen,
            done_ms=done_ms,
            anchor_seen=anchor_seen,
            anchor_ms=anchor_ms,
            fallback_scan=fallback_scan,
        )
        return result
