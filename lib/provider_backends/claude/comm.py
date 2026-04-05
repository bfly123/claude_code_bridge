"""
Claude communication module.

Reads replies from ~/.claude/projects/<project-key>/<session-id>.jsonl and
sends prompts by injecting text into the Claude pane via the configured backend.
"""

from __future__ import annotations

from terminal_runtime.backend_env import apply_backend_env

from .comm_runtime import (
    CLAUDE_PROJECTS_ROOT,
    publish_claude_registry,
    remember_claude_session_binding,
)
from .registry_support.pathing import (
    project_key_for_path as _project_key_for_path,
)
from .comm_runtime.communicator_facade import ClaudeCommunicator
from .comm_runtime.log_reader_facade import ClaudeLogReader

apply_backend_env()
