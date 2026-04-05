"""
Data classes and types for the memory module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ConversationEntry:
    """A single message in a conversation."""
    role: str  # "user" or "assistant"
    content: str
    uuid: Optional[str] = None
    parent_uuid: Optional[str] = None
    timestamp: Optional[str] = None
    tool_calls: list[dict] = field(default_factory=list)


@dataclass
class ToolExecution:
    """A complete tool execution with input and result."""
    tool_id: str
    name: str
    input: dict
    result: Optional[str] = None
    is_error: bool = False


@dataclass
class SessionStats:
    """Statistics about a session's activity."""
    tool_calls: dict[str, int] = field(default_factory=dict)  # tool_name -> count
    tool_executions: list[ToolExecution] = field(default_factory=list)  # 完整工具执行记录
    files_written: list[str] = field(default_factory=list)
    files_read: list[str] = field(default_factory=list)
    files_edited: list[str] = field(default_factory=list)
    bash_commands: list[str] = field(default_factory=list)
    tasks_created: int = 0
    tasks_completed: int = 0


@dataclass
class TransferContext:
    """Context prepared for transfer to another provider."""
    conversations: list[tuple[str, str]]  # List of (user_msg, assistant_msg) pairs
    source_session_id: str
    token_estimate: int
    metadata: dict = field(default_factory=dict)
    stats: Optional[SessionStats] = None
    source_provider: str = "claude"


@dataclass
class SessionInfo:
    """Information about a session."""
    session_id: str
    session_path: str
    project_path: Optional[str] = None
    is_sidechain: bool = False
    last_modified: Optional[float] = None
    provider: Optional[str] = None


class SessionNotFoundError(Exception):
    """Raised when no session can be found."""
    pass


class SessionParseError(Exception):
    """Raised when session parsing fails."""
    pass
