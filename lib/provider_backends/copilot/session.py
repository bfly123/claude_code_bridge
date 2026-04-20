"""
Copilot project session management.

Simplified session binding for GitHub Copilot CLI — no JSONL session binding,
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
        session_filename=".copilot-session",
        instance=instance,
    )


class CopilotProjectSession(PaneLogProjectSessionBase):
    def backend(self):
        return get_backend_for_session(self.data)


def load_project_session(work_dir: Path, instance: Optional[str] = None) -> Optional[CopilotProjectSession]:
    return load_project_session_for_provider(
        work_dir,
        session_filename=".copilot-session",
        session_cls=CopilotProjectSession,
        instance=instance,
    )


def compute_session_key(session: CopilotProjectSession, instance: Optional[str] = None) -> str:
    return compute_session_key_for_provider(session, provider="copilot", instance=instance)


def build_session_binding():
    return build_session_binding_for_provider(provider="copilot", load_session=load_project_session)


__all__ = [
    'CopilotProjectSession',
    'build_session_binding',
    'compute_session_key',
    'find_project_session_file',
    'load_project_session',
]
