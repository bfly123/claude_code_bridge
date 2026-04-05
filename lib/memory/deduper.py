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
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            skip = False
            for pattern in self._protocol_re:
                if pattern.match(line):
                    skip = True
                    break
            if not skip:
                cleaned.append(line)
        return "\n".join(cleaned)

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
            # Normalize and hash content
            normalized = self._normalize_for_hash(entry.content)
            content_hash = f"{entry.role}:{hash(normalized)}"

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
                # Summarize tool calls
                summary = self._summarize_tools(entry.tool_calls)
                if entry.content:
                    new_content = f"{entry.content}\n\n[Tools: {summary}]"
                else:
                    new_content = f"[Tools: {summary}]"
                result.append(ConversationEntry(
                    role=entry.role,
                    content=new_content,
                    uuid=entry.uuid,
                    parent_uuid=entry.parent_uuid,
                    timestamp=entry.timestamp,
                    tool_calls=[],  # Clear after summarizing
                ))
            else:
                result.append(entry)

        return result

    def _summarize_tools(self, tool_calls: list[dict]) -> str:
        """Summarize tool calls into a brief description."""
        if not tool_calls:
            return ""

        # Group by tool name
        by_name: dict[str, list[dict]] = {}
        for tc in tool_calls:
            name = tc.get("name", "unknown")
            by_name.setdefault(name, []).append(tc)

        parts = []
        for name, calls in by_name.items():
            if name in ("Read", "Glob", "Grep"):
                # Extract file paths
                files = []
                for c in calls:
                    inp = c.get("input", {})
                    if isinstance(inp, dict):
                        path = inp.get("file_path") or inp.get("path") or inp.get("pattern")
                        if path:
                            files.append(str(path).split("/")[-1])
                if files:
                    parts.append(f"{name} {len(calls)} file(s): {', '.join(files[:3])}")
                else:
                    parts.append(f"{name} {len(calls)} file(s)")
            elif name in ("Edit", "Write"):
                files = []
                for c in calls:
                    inp = c.get("input", {})
                    if isinstance(inp, dict):
                        path = inp.get("file_path")
                        if path:
                            files.append(str(path).split("/")[-1])
                if files:
                    parts.append(f"{name} {len(calls)} file(s): {', '.join(files[:3])}")
                else:
                    parts.append(f"{name} {len(calls)} file(s)")
            elif name == "Bash":
                parts.append(f"Bash {len(calls)} command(s)")
            else:
                parts.append(f"{name} x{len(calls)}")

        return "; ".join(parts)
