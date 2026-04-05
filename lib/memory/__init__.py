"""
CCB Memory Module - Context transfer and session management.

This module provides memory-related features for CCB, including:
- Context transfer between AI providers
- Claude session parsing
- Conversation deduplication and cleaning
"""

__version__ = "1.0.0"

from .types import (
    ConversationEntry,
    TransferContext,
    SessionInfo,
    SessionStats,
    ToolExecution,
    SessionNotFoundError,
    SessionParseError,
)

from .session_parser import (
    ClaudeSessionParser,
    CLAUDE_PROJECTS_ROOT,
)

from .deduper import (
    ConversationDeduper,
    PROTOCOL_PATTERNS,
    SYSTEM_NOISE_PATTERNS,
)

from .formatter import (
    ContextFormatter,
)

from .transfer import (
    ContextTransfer,
)

__all__ = [
    # Types
    "ConversationEntry",
    "TransferContext",
    "SessionInfo",
    "SessionStats",
    "ToolExecution",
    "SessionNotFoundError",
    "SessionParseError",
    # Parser
    "ClaudeSessionParser",
    "CLAUDE_PROJECTS_ROOT",
    # Deduper
    "ConversationDeduper",
    "PROTOCOL_PATTERNS",
    "SYSTEM_NOISE_PATTERNS",
    # Formatter
    "ContextFormatter",
    # Transfer
    "ContextTransfer",
]
