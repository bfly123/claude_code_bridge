from __future__ import annotations

import json
from typing import Optional

from memory.types import SessionStats, TransferContext

from .common import provider_label, transfer_timestamp
from .tools import format_stats_section, format_tool_executions, format_tool_input


class ContextFormatter:
    CHARS_PER_TOKEN = 4

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens

    @staticmethod
    def _provider_label(provider: Optional[str]) -> str:
        return provider_label(provider)

    def _format_tool_input(self, name: str, inp: dict) -> str:
        return format_tool_input(name, inp)

    def _format_tool_executions(self, executions: list, detailed: bool) -> list[str]:
        return format_tool_executions(executions, detailed=detailed)

    def _format_stats_section(self, stats: Optional[SessionStats], detailed: bool = False) -> list[str]:
        return format_stats_section(stats, detailed=detailed)

    def estimate_tokens(self, text: str) -> int:
        return len(text) // self.CHARS_PER_TOKEN

    def truncate_to_limit(
        self,
        conversations: list[tuple[str, str]],
        max_tokens: Optional[int] = None,
    ) -> list[tuple[str, str]]:
        limit = max_tokens or self.max_tokens
        result: list[tuple[str, str]] = []
        total_tokens = 0
        for user_msg, assistant_msg in reversed(conversations):
            pair_tokens = self.estimate_tokens(user_msg + assistant_msg)
            if total_tokens + pair_tokens > limit:
                break
            result.append((user_msg, assistant_msg))
            total_tokens += pair_tokens
        result.reverse()
        return result

    def format_markdown(self, context: TransferContext, detailed: bool = False) -> str:
        provider = self._provider_label(context.source_provider or context.metadata.get('provider'))
        timestamp = transfer_timestamp().strftime('%Y-%m-%d %H:%M:%S')
        lines = [
            f'## Context Transfer from {provider} Session',
            '',
            f'**IMPORTANT**: This is a context handoff from a {provider} session.',
            'The previous AI assistant completed the work described below.',
            'Please review and continue from where it left off.',
            '',
            f'**Source Provider**: {provider}',
            f'**Source Session**: {context.source_session_id}',
            f'**Transferred**: {timestamp}',
            f'**Conversations**: {len(context.conversations)}',
            '',
            '---',
            '',
        ]
        if context.stats:
            lines.extend(self._format_stats_section(context.stats, detailed=detailed))
        lines.extend(['### Previous Conversation Context', ''])
        for index, (user_msg, assistant_msg) in enumerate(context.conversations, 1):
            lines.extend(
                [
                    f'#### Turn {index}',
                    f'**User**: {user_msg}',
                    '',
                    f'**Assistant**: {assistant_msg}',
                    '',
                    '---',
                    '',
                ]
            )
        lines.append('**Action Required**: Review the above context and continue the work.')
        return '\n'.join(lines)

    def format_plain(self, context: TransferContext) -> str:
        provider = self._provider_label(context.source_provider or context.metadata.get('provider'))
        timestamp = transfer_timestamp().strftime('%Y-%m-%d %H:%M:%S')
        lines = [
            f'=== Context Transfer from {provider} ===',
            f'Provider: {provider}',
            f'Session: {context.source_session_id}',
            f'Transferred: {timestamp}',
            f'Conversations: {len(context.conversations)}',
            '',
            '=== Previous Conversation ===',
            '',
        ]
        for index, (user_msg, assistant_msg) in enumerate(context.conversations, 1):
            lines.extend(
                [
                    f'--- Turn {index} ---',
                    f'User: {user_msg}',
                    '',
                    f'Assistant: {assistant_msg}',
                    '',
                ]
            )
        lines.append('=== End of Context ===')
        return '\n'.join(lines)

    def format_json(self, context: TransferContext) -> str:
        provider = str(context.source_provider or context.metadata.get('provider') or 'claude').strip().lower()
        data = {
            'source_provider': provider,
            'source_session_id': context.source_session_id,
            'transferred_at': transfer_timestamp().isoformat(),
            'token_estimate': context.token_estimate,
            'conversations': [{'user': user_msg, 'assistant': assistant_msg} for user_msg, assistant_msg in context.conversations],
            'metadata': context.metadata,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def format(
        self,
        context: TransferContext,
        fmt: str = 'markdown',
        detailed: bool = False,
    ) -> str:
        if fmt == 'plain':
            return self.format_plain(context)
        if fmt == 'json':
            return self.format_json(context)
        return self.format_markdown(context, detailed=detailed)


__all__ = ['ContextFormatter']
