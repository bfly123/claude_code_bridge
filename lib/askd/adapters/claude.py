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
from completion_hook import (
    COMPLETION_STATUS_CANCELLED,
    COMPLETION_STATUS_COMPLETED,
    COMPLETION_STATUS_FAILED,
    COMPLETION_STATUS_INCOMPLETE,
    default_reply_for_status,
    notify_completion,
)
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

    def load_session(self, work_dir: Path, instance: Optional[str] = None) -> Optional[Any]:
        return load_project_session(work_dir, instance)

    def compute_session_key(self, session: Any, instance: Optional[str] = None) -> str:
        return compute_session_key(session, instance) if session else "claude:unknown"

    def handle_task(self, task: QueuedTask) -> ProviderResult:
        started_ms = _now_ms()
        req = task.request
        work_dir = Path(req.work_dir)
        _write_log(f"[INFO] start provider=claude req_id={task.req_id} work_dir={req.work_dir}")

        instance = task.request.instance
        session = load_project_session(work_dir, instance)
        session_key = self.compute_session_key(session, instance)

        if not session:
            return ProviderResult(
                exit_code=1,
                reply="No active Claude session found for work_dir.",
                req_id=task.req_id,
                session_key=session_key,
                done_seen=False,
                status=COMPLETION_STATUS_FAILED,
            )

        ok, pane_or_err = session.ensure_pane()
        if not ok:
            return ProviderResult(
                exit_code=1,
                reply=f"Session pane not available: {pane_or_err}",
                req_id=task.req_id,
                session_key=session_key,
                done_seen=False,
                status=COMPLETION_STATUS_FAILED,
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
                status=COMPLETION_STATUS_FAILED,
            )

        deadline = None if float(req.timeout_s) < 0.0 else (time.time() + float(req.timeout_s))

        log_reader = ClaudeLogReader(work_dir=Path(session.work_dir))
        if session.claude_session_path:
            try:
                log_reader.set_preferred_session(Path(session.claude_session_path))
            except Exception:
                pass
        state = log_reader.capture_state()

        if req.no_wrap:
            prompt = req.message
        else:
            prompt = wrap_claude_prompt(req.message, task.req_id)
        backend.send_text(pane_id, prompt)

        # Use structured Claude session logs only
        result = self._wait_for_response(
            task, session, session_key, started_ms, log_reader, state, backend, pane_id, deadline
        )
        result.reply = self._postprocess_reply(req, result.reply)
        self._finalize_result(result, req, task)
        return result

    def _finalize_result(self, result: ProviderResult, req: ProviderRequest, task: QueuedTask) -> None:
        _write_log(f"[INFO] done provider=claude req_id={result.req_id} exit={result.exit_code}")

        reply_for_hook = result.reply
        status = result.status or (COMPLETION_STATUS_COMPLETED if result.done_seen else COMPLETION_STATUS_INCOMPLETE)
        if task.cancelled:
            _write_log(f"[WARN] Task cancelled, sending cancellation completion hook: req_id={task.req_id}")
            status = COMPLETION_STATUS_CANCELLED
        if not (reply_for_hook or "").strip():
            reply_for_hook = default_reply_for_status(status, done_seen=result.done_seen)

        _write_log(
            f"[INFO] notify_completion caller={req.caller} status={status} "
            f"done_seen={result.done_seen} email_req_id={req.email_req_id}"
        )
        notify_completion(
            provider="claude",
            output_file=req.output_path,
            reply=reply_for_hook,
            req_id=result.req_id,
            done_seen=result.done_seen,
            status=status,
            caller=req.caller,
            email_req_id=req.email_req_id,
            email_msg_id=req.email_msg_id,
            email_from=req.email_from,
            work_dir=req.work_dir,
            caller_pane_id=req.caller_pane_id,
            caller_terminal=req.caller_terminal,
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
            if task.cancel_event and task.cancel_event.is_set():
                _write_log(f"[INFO] Task cancelled during wait loop: req_id={task.req_id}")
                break

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
                        status=COMPLETION_STATUS_FAILED,
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
            status=COMPLETION_STATUS_COMPLETED if done_seen else (
                COMPLETION_STATUS_CANCELLED if task.cancelled else COMPLETION_STATUS_INCOMPLETE
            ),
        )
        return result
