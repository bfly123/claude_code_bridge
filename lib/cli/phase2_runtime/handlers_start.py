from __future__ import annotations

import os
import sys

from cli.services.start_foreground import attach_started_project_namespace


def _stream_is_tty(stream: object) -> bool:
    checker = getattr(stream, 'isatty', None)
    if not callable(checker):
        return False
    try:
        return bool(checker())
    except Exception:
        return False


def handle_config_validate(context, command, out, services) -> int:
    del command
    summary = services.validate_config_context(context)
    services.write_lines(out, services.render_config_validate(summary))
    return 0


def handle_start(context, command, out, services) -> int:
    summary = services.start_agents(context, command)
    if not _env_truthy('CCB_NO_ATTACH') and _stream_is_tty(sys.stdin) and _stream_is_tty(out):
        attach_started_project_namespace(context)
        return 0
    services.write_lines(out, services.render_start(summary))
    return 0


def _env_truthy(name: str) -> bool:
    value = str(os.environ.get(name) or '').strip().lower()
    return value in {'1', 'true', 'yes', 'on'}


__all__ = ['handle_config_validate', 'handle_start']
