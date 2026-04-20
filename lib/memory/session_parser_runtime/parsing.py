from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from memory.types import ConversationEntry, SessionNotFoundError, SessionParseError


def parse_session(parser, session_path: Path) -> list[ConversationEntry]:
    if not session_path.exists():
        raise SessionNotFoundError(f"Session file not found: {session_path}")

    entries: list[ConversationEntry] = []
    errors = 0
    total = 0

    try:
        content = session_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise SessionParseError(f"Failed to read session file: {exc}")

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        total += 1
        try:
            obj = json.loads(line)
            entry = parse_entry(parser, obj)
            if entry:
                entries.append(entry)
        except json.JSONDecodeError:
            errors += 1
            continue

    if total > 0 and errors / total > 0.5:
        raise SessionParseError(f"Too many parse errors: {errors}/{total} lines failed")

    return entries


def parse_entry(parser, obj: dict) -> Optional[ConversationEntry]:
    if not isinstance(obj, dict):
        return None

    msg_type = obj.get("type")
    if msg_type == "user":
        content = extract_content(parser, obj.get("message", {}))
        if content:
            return ConversationEntry(
                role="user",
                content=content,
                uuid=obj.get("uuid"),
                parent_uuid=obj.get("parentUuid"),
                timestamp=obj.get("timestamp"),
            )

    if msg_type == "assistant":
        message = obj.get("message", {})
        content = extract_content(parser, message)
        tool_calls = extract_tool_calls(parser, message)
        if content or tool_calls:
            return ConversationEntry(
                role="assistant",
                content=content,
                uuid=obj.get("uuid"),
                parent_uuid=obj.get("parentUuid"),
                timestamp=obj.get("timestamp"),
                tool_calls=tool_calls,
            )

    return None


def extract_content(parser, message: dict) -> str:
    del parser
    if not isinstance(message, dict):
        return ""

    content = message.get("content")
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    texts.append(block.get("text", ""))
            elif isinstance(block, str):
                texts.append(block)
        return "\n".join(texts)

    return ""


def extract_tool_calls(parser, message: dict) -> list[dict]:
    del parser
    if not isinstance(message, dict):
        return []

    content = message.get("content")
    if not isinstance(content, list):
        return []

    tool_calls = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            tool_calls.append(
                {
                    "name": block.get("name", ""),
                    "input": block.get("input", {}),
                }
            )
    return tool_calls


__all__ = ["extract_content", "extract_tool_calls", "parse_entry", "parse_session"]
