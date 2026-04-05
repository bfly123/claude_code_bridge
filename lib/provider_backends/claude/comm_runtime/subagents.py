from __future__ import annotations

from pathlib import Path
from typing import Any

from .incremental_io import read_incremental_jsonl
from .parsing import extract_message


def subagent_state_for_session(reader, session: Path, *, start_from_end: bool) -> dict[str, dict[str, Any]]:
    logs = list_subagent_logs(reader, session)
    state: dict[str, dict[str, Any]] = {}
    for log_path in logs:
        key = str(log_path)
        try:
            size = log_path.stat().st_size
        except OSError:
            size = 0
        state[key] = {"offset": size if start_from_end else 0, "carry": b""}
    return state


def list_subagent_logs(reader, session: Path) -> list[Path]:
    session_dir = session.with_suffix("")
    sub_dir = session_dir / "subagents"
    if not sub_dir.exists():
        return []
    return sorted([path for path in sub_dir.glob("*.jsonl") if path.is_file()])


def format_subagent_text(reader, text: str, entry: dict[str, Any]) -> str:
    if not reader._subagent_tag:
        return text
    agent_id = str(entry.get("agentId") or "").strip()
    slug = str(entry.get("slug") or "").strip()
    label = reader._subagent_tag
    if agent_id:
        label = f"{label}:{agent_id}"
    if slug:
        label = f"{label} {slug}"
    return f"{label}\n{text}"


def read_new_subagent_events(reader, session: Path, state: dict[str, Any]) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    sub_state = state.get("subagents")
    if not isinstance(sub_state, dict):
        sub_state = {}
    logs = list_subagent_logs(reader, session)
    new_state: dict[str, dict[str, Any]] = {}
    events: list[tuple[str, str]] = []

    for log_path in logs:
        key = str(log_path)
        log_state = sub_state.get(key) if isinstance(sub_state, dict) else None
        offset = 0
        carry = b""
        if isinstance(log_state, dict):
            offset = int(log_state.get("offset") or 0)
            carry = log_state.get("carry") or b""

        sub_events, updated = read_new_events_for_file(reader, log_path, offset, carry)
        for role, text, entry in sub_events:
            if role == "user" and not reader._include_subagent_user:
                continue
            events.append((role, format_subagent_text(reader, text, entry)))

        new_state[key] = {"offset": updated["offset"], "carry": updated["carry"]}

    return events, new_state


def read_new_events_for_file(
    reader, path: Path, offset: int, carry: bytes
) -> tuple[list[tuple[str, str, dict[str, Any]]], dict[str, Any]]:
    raw_entries, updated = read_incremental_jsonl(path, offset, carry)
    events: list[tuple[str, str, dict[str, Any]]] = []
    for entry in raw_entries:
        user_msg = extract_message(entry, "user")
        if user_msg:
            events.append(("user", user_msg, entry))
            continue
        assistant_msg = extract_message(entry, "assistant")
        if assistant_msg:
            events.append(("assistant", assistant_msg, entry))
    return events, updated


__all__ = [
    "format_subagent_text",
    "list_subagent_logs",
    "read_new_events_for_file",
    "read_new_subagent_events",
    "subagent_state_for_session",
]
