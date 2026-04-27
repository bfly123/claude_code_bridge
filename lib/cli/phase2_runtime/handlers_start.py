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
    interactive_attach = (
        not _env_truthy('CCB_NO_ATTACH')
        and _stream_is_tty(sys.stdin)
        and _stream_is_tty(out)
    )
    terminal_size = _terminal_size_for_streams(out, sys.stdin) if interactive_attach else None
    if terminal_size is not None:
        summary = services.start_agents(context, command, terminal_size=terminal_size)
    else:
        summary = services.start_agents(context, command)
    if interactive_attach:
        attach_started_project_namespace(context)
        return 0
    services.write_lines(out, services.render_start(summary))
    return 0


def _env_truthy(name: str) -> bool:
    value = str(os.environ.get(name) or '').strip().lower()
    return value in {'1', 'true', 'yes', 'on'}


def _terminal_size_for_streams(*streams: object) -> tuple[int, int] | None:
    for stream in streams:
        fileno = getattr(stream, 'fileno', None)
        if not callable(fileno):
            continue
        try:
            fd = int(fileno())
        except Exception:
            continue
        try:
            size = os.get_terminal_size(fd)
        except OSError:
            continue
        columns = int(getattr(size, 'columns', 0) or 0)
        lines = int(getattr(size, 'lines', 0) or 0)
        if columns > 0 and lines > 0:
            return columns, lines
    return None


__all__ = ['handle_config_validate', 'handle_start']
