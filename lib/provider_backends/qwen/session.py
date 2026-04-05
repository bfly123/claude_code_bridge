"""
Qwen project session management.

Simplified session binding for GitHub Qwen CLI — no JSONL session binding,
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
        session_filename=".qwen-session",
        instance=instance,
    )


class QwenProjectSession(PaneLogProjectSessionBase):
    def backend(self):
        return get_backend_for_session(self.data)


def load_project_session(work_dir: Path, instance: Optional[str] = None) -> Optional[QwenProjectSession]:
    return load_project_session_for_provider(
        work_dir,
        session_filename=".qwen-session",
        session_cls=QwenProjectSession,
        instance=instance,
    )


def compute_session_key(session: QwenProjectSession, instance: Optional[str] = None) -> str:
    return compute_session_key_for_provider(session, provider="qwen", instance=instance)


def build_session_binding():
    return build_session_binding_for_provider(provider="qwen", load_session=load_project_session)


__all__ = [
    'QwenProjectSession',
    'build_session_binding',
    'compute_session_key',
    'find_project_session_file',
    'load_project_session',
]
