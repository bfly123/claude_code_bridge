from __future__ import annotations

from pathlib import Path
from typing import Optional

from terminal_runtime.backend_env import apply_backend_env
from provider_core.contracts import ProviderSessionBinding

from .session_runtime import (
    ClaudeProjectSession,
    compute_session_key as _compute_session_key_impl,
    find_project_session_file as _find_project_session_file_impl,
    load_project_session as _load_project_session_impl,
)

apply_backend_env()


def find_project_session_file(work_dir: Path, instance: Optional[str] = None) -> Optional[Path]:
    return _find_project_session_file_impl(work_dir, instance)


def load_project_session(work_dir: Path, instance: Optional[str] = None) -> Optional[ClaudeProjectSession]:
    return _load_project_session_impl(work_dir, instance)


def compute_session_key(session: ClaudeProjectSession, instance: Optional[str] = None) -> str:
    return _compute_session_key_impl(session, instance)


def build_session_binding() -> ProviderSessionBinding:
    return ProviderSessionBinding(
        provider='claude',
        load_session=load_project_session,
        session_id_attr='claude_session_id',
        session_path_attr='claude_session_path',
    )


__all__ = [
    'ClaudeProjectSession',
    'build_session_binding',
    'compute_session_key',
    'find_project_session_file',
    'load_project_session',
]
