from __future__ import annotations


def follow_workspace_sessions(reader) -> bool:
    return bool(getattr(reader, "_follow_workspace_sessions", False) and getattr(reader, "_work_dir", None))


__all__ = ['follow_workspace_sessions']
