from __future__ import annotations

__all__ = [
    "CCB_PROJECT_CONFIG_DIRNAME",
    "HAS_WATCHDOG",
    "SessionFileWatcher",
    "check_session_writable",
    "find_project_session_file",
    "print_session_error",
    "project_config_dir",
    "resolve_project_config_dir",
    "resolve_work_dir",
    "resolve_work_dir_with_registry",
    "safe_write_session",
]


def __getattr__(name: str):
    if name in {
        'CCB_PROJECT_CONFIG_DIRNAME',
        'check_session_writable',
        'find_project_session_file',
        'print_session_error',
        'project_config_dir',
        'resolve_project_config_dir',
        'safe_write_session',
    }:
        from . import files as _files

        return getattr(_files, name)
    if name in {'resolve_work_dir', 'resolve_work_dir_with_registry'}:
        from . import resolution as _resolution

        return getattr(_resolution, name)
    if name in {'HAS_WATCHDOG', 'SessionFileWatcher'}:
        from . import watch as _watch

        return getattr(_watch, name)
    raise AttributeError(name)
