"""
CodeBuddy project session management.

Simplified session binding for GitHub CodeBuddy CLI — no JSONL session binding,
pane-log based communication only.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from terminal_runtime.backend_env import apply_backend_env
from terminal_runtime import get_backend_for_session
from provider_backends.pane_log_support.session import (
    PaneLogProjectSessionBase,
    build_session_binding_for_provider,
    compute_session_key_for_provider,
    find_project_session_file_for_provider,
    load_project_session_for_provider,
)

apply_backend_env()


def find_project_session_file(work_dir: Path, instance: Optional[str] = None) -> Optional[Path]:
    return find_project_session_file_for_provider(
        work_dir,
        session_filename=".codebuddy-session",
        instance=instance,
    )


class CodebuddyProjectSession(PaneLogProjectSessionBase):
    def backend(self):
        return get_backend_for_session(self.data)


def load_project_session(work_dir: Path, instance: Optional[str] = None) -> Optional[CodebuddyProjectSession]:
    return load_project_session_for_provider(
        work_dir,
        session_filename=".codebuddy-session",
        session_cls=CodebuddyProjectSession,
        instance=instance,
    )


def compute_session_key(session: CodebuddyProjectSession, instance: Optional[str] = None) -> str:
    return compute_session_key_for_provider(session, provider="codebuddy", instance=instance)


def build_session_binding():
    return build_session_binding_for_provider(provider="codebuddy", load_session=load_project_session)


__all__ = [
    'CodebuddyProjectSession',
    'build_session_binding',
    'compute_session_key',
    'find_project_session_file',
    'load_project_session',
]
