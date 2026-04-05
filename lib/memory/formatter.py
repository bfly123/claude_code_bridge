"""
Format conversation context for output.

Supports markdown, plain text, and JSON formats with token estimation.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from .types import TransferContext, SessionStats


class ContextFormatter:
    """Format conversation context for different output formats."""

    # Rough estimate: 1 token ~= 4 characters
    CHARS_PER_TOKEN = 4

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens

    @staticmethod
    def _provider_label(provider: Optional[str]) -> str:
        key = (provider or "claude").strip().lower()
        mapping = {
            "claude": "Claude",
            "codex": "Codex",
            "gemini": "Gemini",
            "opencode": "OpenCode",
            "droid": "Droid",
            "auto": "Auto",
        }
        if key in mapping:
            return mapping[key]
        return provider.strip().title() if provider else "Claude"

    def _format_tool_input(self, name: str, inp: dict) -> str:
        """Format tool input for display."""
        if not inp:
            return ""
        if name == "Write":
            return inp.get("file_path", "")
        if name == "Edit":
            return inp.get("file_path", "")
        if name == "Bash":
            cmd = inp.get("command", "")
            return cmd[:80] + "..." if len(cmd) > 80 else cmd
        if name == "TaskCreate":
            return inp.get("subject", "")
        if name == "TaskUpdate":
            return f"#{inp.get('taskId', '')} -> {inp.get('status', '')}"
        return ""

    def _format_tool_executions(self, executions: list, detailed: bool) -> list[str]:
        """Format tool executions section."""
        lines = []

        if detailed:
            lines.append("**All Tool Executions:**")
            lines.append("")
            for i, ex in enumerate(executions):
                lines.append(f"#### {i+1}. {ex.name}" + (" ❌" if ex.is_error else ""))
                inp_str = self._format_tool_input(ex.name, ex.input)
                if inp_str:
                    lines.append(f"- **Input**: `{inp_str}`")
                if ex.result:
                    result = str(ex.result)
                    lines.append("- **Result**:")
                    lines.append("```")
                    lines.append(result)
                    lines.append("```")
                lines.append("")
        else:
            lines.append("**Recent Tool Executions:**")
            lines.append("")
            shown = 0
            for ex in executions[-10:]:
                if ex.name in ("Read", "Glob", "Grep"):
                    continue
                lines.append(f"- **{ex.name}**" + (" ❌" if ex.is_error else ""))
                inp_str = self._format_tool_input(ex.name, ex.input)
                if inp_str:
                    lines.append(f"  - Input: {inp_str}")
                if ex.result:
                    preview = str(ex.result)[:150].replace("\n", " ")
                    if len(str(ex.result)) > 150:
                        preview += "..."
                    lines.append(f"  - Result: `{preview}`")
                shown += 1
                if shown >= 5:
                    break
            if len(executions) > 5:
                lines.append(f"- ... and {len(executions) - 5} more")
            lines.append("")

        return lines

    def _format_stats_section(self, stats: Optional[SessionStats], detailed: bool = False) -> list[str]:
        """Format session stats as markdown lines."""
        if not stats:
            return []

        lines = ["### Session Activity Summary", ""]

        # Tool calls
        if stats.tool_calls:
            lines.append("**Tool Calls:**")
            for name, count in sorted(stats.tool_calls.items(), key=lambda x: -x[1]):
                lines.append(f"- {name}: {count}")
            lines.append("")

        # Files written
        if stats.files_written:
            lines.append("**Files Created/Written:**")
            limit = 50 if detailed else 15
            for f in stats.files_written[:limit]:
                lines.append(f"- `{f}`")
            if len(stats.files_written) > limit:
                lines.append(f"- ... and {len(stats.files_written) - limit} more")
            lines.append("")

        # Files edited
        if stats.files_edited:
            lines.append("**Files Edited:**")
            limit = 30 if detailed else 10
            for f in stats.files_edited[:limit]:
                lines.append(f"- `{f}`")
            lines.append("")

        # Files read
        if stats.files_read:
            lines.append("**Files Read:**")
            limit = 30 if detailed else 10
            for f in stats.files_read[:limit]:
                lines.append(f"- `{f}`")
            if len(stats.files_read) > limit:
                lines.append(f"- ... and {len(stats.files_read) - limit} more")
            lines.append("")

        # Tasks
        if stats.tasks_created > 0:
            lines.append(f"**Tasks:** {stats.tasks_completed}/{stats.tasks_created} completed")
            lines.append("")

        # Tool executions
        if stats.tool_executions:
            lines.extend(self._format_tool_executions(stats.tool_executions, detailed))

        lines.append("---")
        lines.append("")
        return lines

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return len(text) // self.CHARS_PER_TOKEN

    def truncate_to_limit(
        self,
        conversations: list[tuple[str, str]],
        max_tokens: Optional[int] = None,
    ) -> list[tuple[str, str]]:
        """Truncate conversations to fit within token limit (oldest first)."""
        limit = max_tokens or self.max_tokens
        result: list[tuple[str, str]] = []
        total_tokens = 0

        # Process from newest to oldest, then reverse
        for user_msg, assistant_msg in reversed(conversations):
            pair_tokens = self.estimate_tokens(user_msg + assistant_msg)
            if total_tokens + pair_tokens > limit:
                break
            result.append((user_msg, assistant_msg))
            total_tokens += pair_tokens

        result.reverse()
        return result

    def format_markdown(self, context: TransferContext, detailed: bool = False) -> str:
        """Format context as markdown."""
        provider = self._provider_label(
            context.source_provider or context.metadata.get("provider")
        )
        lines = [
            f"## Context Transfer from {provider} Session",
            "",
            f"**IMPORTANT**: This is a context handoff from a {provider} session.",
            "The previous AI assistant completed the work described below.",
            "Please review and continue from where it left off.",
            "",
            f"**Source Provider**: {provider}",
            f"**Source Session**: {context.source_session_id}",
            f"**Transferred**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Conversations**: {len(context.conversations)}",
            "",
            "---",
            "",
        ]

        # Add stats section if available
        if context.stats:
            lines.extend(self._format_stats_section(context.stats, detailed=detailed))

        lines.append("### Previous Conversation Context")
        lines.append("")

        for i, (user_msg, assistant_msg) in enumerate(context.conversations, 1):
            lines.append(f"#### Turn {i}")
            lines.append(f"**User**: {user_msg}")
            lines.append("")
            lines.append(f"**Assistant**: {assistant_msg}")
            lines.append("")
            lines.append("---")
            lines.append("")

        lines.append("**Action Required**: Review the above context and continue the work.")
        return "\n".join(lines)

    def format_plain(self, context: TransferContext) -> str:
        """Format context as plain text."""
        provider = self._provider_label(
            context.source_provider or context.metadata.get("provider")
        )
        lines = [
            f"=== Context Transfer from {provider} ===",
            f"Provider: {provider}",
            f"Session: {context.source_session_id}",
            f"Transferred: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Conversations: {len(context.conversations)}",
            "",
            "=== Previous Conversation ===",
            "",
        ]

        for i, (user_msg, assistant_msg) in enumerate(context.conversations, 1):
            lines.append(f"--- Turn {i} ---")
            lines.append(f"User: {user_msg}")
            lines.append("")
            lines.append(f"Assistant: {assistant_msg}")
            lines.append("")

        lines.append("=== End of Context ===")
        return "\n".join(lines)

    def format_json(self, context: TransferContext) -> str:
        """Format context as JSON."""
        provider = (context.source_provider or context.metadata.get("provider") or "claude").strip().lower()
        data = {
            "source_provider": provider,
            "source_session_id": context.source_session_id,
            "transferred_at": datetime.now().isoformat(),
            "token_estimate": context.token_estimate,
            "conversations": [
                {"user": u, "assistant": a}
                for u, a in context.conversations
            ],
            "metadata": context.metadata,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def format(
        self,
        context: TransferContext,
        fmt: str = "markdown",
        detailed: bool = False,
    ) -> str:
        """Format context in the specified format."""
        if fmt == "plain":
            return self.format_plain(context)
        elif fmt == "json":
            return self.format_json(context)
        else:
            return self.format_markdown(context, detailed=detailed)
