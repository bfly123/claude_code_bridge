"""
Dedupe and clean conversation content.

Removes protocol markers, system noise, and deduplicates messages.
"""

from __future__ import annotations

import re
from typing import Optional

from .types import ConversationEntry


# Protocol markers to remove
PROTOCOL_PATTERNS = [
    r"^\s*CCB_REQ_ID:\s*\d{8}-\d{6}-\d{3}-\d+-\d+\s*$",
    r"^\s*CCB_BEGIN:\s*\d{8}-\d{6}-\d{3}-\d+-\d+\s*$",
    r"^\s*CCB_DONE:\s*\d{8}-\d{6}-\d{3}-\d+-\d+\s*$",
    r"^\s*\[CCB_ASYNC_SUBMITTED[^\]]*\].*$",
    r"^\s*CCB_CALLER=\w+\s*$",
    r"^\s*\[Request interrupted by user for tool use\]\s*$",
    r"^\s*The user doesn't want to proceed with this tool use\..*$",
    r"^\s*User rejected tool use\s*$",
]

# System noise patterns to remove (multiline)
SYSTEM_NOISE_PATTERNS = [
    r"<system-reminder>.*?</system-reminder>",
    r"<env>.*?</env>",
    r"<rules>.*?</rules>",
    r"<!-- CCB_CONFIG_START -->.*?<!-- CCB_CONFIG_END -->",
    r"<local-command-caveat>.*?</local-command-caveat>",
    r"\[CCB_ASYNC_SUBMITTED[^\]]*\][\s\S]*?(?:\n\n|\Z)",
]


class ConversationDeduper:
    """Clean and deduplicate conversation content."""

    def __init__(self):
        self._protocol_re = [re.compile(p, re.MULTILINE) for p in PROTOCOL_PATTERNS]
        self._noise_re = [re.compile(p, re.DOTALL) for p in SYSTEM_NOISE_PATTERNS]

    def strip_protocol_markers(self, text: str) -> str:
        """Remove CCB protocol markers from text."""
        return "\n".join(
            line
            for line in text.split("\n")
            if not self._matches_protocol_marker(line)
        )

    def strip_system_noise(self, text: str) -> str:
        """Remove system noise tags from text."""
        result = text
        for pattern in self._noise_re:
            result = pattern.sub("", result)
        # Clean up extra whitespace
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()

    def clean_content(self, text: str) -> str:
        """Apply all cleaning operations."""
        text = self.strip_protocol_markers(text)
        text = self.strip_system_noise(text)
        return text.strip()

    def dedupe_messages(
        self, entries: list[ConversationEntry]
    ) -> list[ConversationEntry]:
        """Remove duplicate consecutive messages."""
        if not entries:
            return []

        result: list[ConversationEntry] = []
        prev_hash: Optional[str] = None

        for entry in entries:
            content_hash = self._content_hash(entry)

            if content_hash != prev_hash:
                result.append(entry)
                prev_hash = content_hash

        return result

    def _normalize_for_hash(self, text: str) -> str:
        """Normalize text for hash comparison."""
        # Remove whitespace variations
        text = re.sub(r"\s+", " ", text)
        return text.strip().lower()

    def collapse_tool_calls(
        self, entries: list[ConversationEntry]
    ) -> list[ConversationEntry]:
        """Collapse consecutive tool calls into summaries."""
        if not entries:
            return []

        result: list[ConversationEntry] = []

        for entry in entries:
            if entry.role == "assistant" and entry.tool_calls:
                result.append(self._collapse_tool_entry(entry))
            else:
                result.append(entry)

        return result

    def _matches_protocol_marker(self, line: str) -> bool:
        return any(pattern.match(line) for pattern in self._protocol_re)

    def _content_hash(self, entry: ConversationEntry) -> str:
        normalized = self._normalize_for_hash(entry.content)
        return f"{entry.role}:{hash(normalized)}"

    def _collapse_tool_entry(self, entry: ConversationEntry) -> ConversationEntry:
        summary = self._summarize_tools(entry.tool_calls)
        content = _append_tool_summary(entry.content, summary)
        return ConversationEntry(
            role=entry.role,
            content=content,
            uuid=entry.uuid,
            parent_uuid=entry.parent_uuid,
            timestamp=entry.timestamp,
            tool_calls=[],
        )

    def _summarize_tools(self, tool_calls: list[dict]) -> str:
        """Summarize tool calls into a brief description."""
        if not tool_calls:
            return ""

        parts = []
        for name, calls in _group_tool_calls(tool_calls).items():
            parts.append(_summarize_tool_group(name, calls))

        return "; ".join(parts)


def _append_tool_summary(content: str, summary: str) -> str:
    if content:
        return f"{content}\n\n[Tools: {summary}]"
    return f"[Tools: {summary}]"


def _group_tool_calls(tool_calls: list[dict]) -> dict[str, list[dict]]:
    by_name: dict[str, list[dict]] = {}
    for tool_call in tool_calls:
        name = str(tool_call.get("name", "unknown"))
        by_name.setdefault(name, []).append(tool_call)
    return by_name


def _summarize_tool_group(name: str, calls: list[dict]) -> str:
    if name in ("Read", "Glob", "Grep"):
        return _summarize_file_tool_group(name, calls, keys=("file_path", "path", "pattern"))
    if name in ("Edit", "Write"):
        return _summarize_file_tool_group(name, calls, keys=("file_path",))
    if name == "Bash":
        return f"Bash {len(calls)} command(s)"
    return f"{name} x{len(calls)}"


def _summarize_file_tool_group(name: str, calls: list[dict], *, keys: tuple[str, ...]) -> str:
    files = [_tool_basename(tool_call, keys=keys) for tool_call in calls]
    files = [item for item in files if item]
    if files:
        return f"{name} {len(calls)} file(s): {', '.join(files[:3])}"
    return f"{name} {len(calls)} file(s)"


def _tool_basename(tool_call: dict, *, keys: tuple[str, ...]) -> str | None:
    tool_input = tool_call.get("input", {})
    if not isinstance(tool_input, dict):
        return None
    for key in keys:
        value = tool_input.get(key)
        if value:
            return str(value).split("/")[-1]
    return None
