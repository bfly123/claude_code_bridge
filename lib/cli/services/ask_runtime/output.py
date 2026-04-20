from __future__ import annotations

from pathlib import Path

from cli.output import EXIT_ERROR, EXIT_NO_REPLY, EXIT_OK, atomic_write_text


def exit_code_for_ask_status(status: str | None, *, reply: str) -> int:
    normalized = str(status or '').strip().lower()
    if normalized == 'completed':
        return EXIT_OK
    if normalized == 'incomplete':
        return EXIT_NO_REPLY if reply else EXIT_ERROR
    return EXIT_ERROR


def write_ask_output(path: str | Path, reply: str) -> None:
    content = reply + ('\n' if reply and not reply.endswith('\n') else '')
    atomic_write_text(Path(path), content)


__all__ = ['exit_code_for_ask_status', 'write_ask_output']
