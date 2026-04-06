from __future__ import annotations

import os
from typing import Sequence


def looks_like_config_validate(argv: Sequence[str]) -> bool:
    tokens = list(argv)
    index = 0
    while index < len(tokens) and tokens[index] == '--project':
        index += 2
    remaining = tokens[index:]
    return bool(remaining) and remaining[0] == 'config'


def should_auto_open_after_start(command, *, out, stdin) -> bool:
    del command
    if env_truthy('CCB_NO_AUTO_OPEN'):
        return False
    return stream_is_tty(stdin) and stream_is_tty(out)


def stream_is_tty(stream: object) -> bool:
    checker = getattr(stream, 'isatty', None)
    if not callable(checker):
        return False
    try:
        return bool(checker())
    except Exception:
        return False


def env_truthy(name: str) -> bool:
    value = str(os.environ.get(name) or '').strip().lower()
    return value in {'1', 'true', 'yes', 'on'}


__all__ = ['env_truthy', 'looks_like_config_validate', 'should_auto_open_after_start', 'stream_is_tty']
