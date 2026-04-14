from __future__ import annotations

import argparse

from cli.models import ParsedStartCommand

from .common import parse_args

_REMOVED_START_FLAGS = {'-a', '--auto', '-r', '--resume', '--restore'}


def parse_global_options(tokens: list[str], *, error_type) -> tuple[str | None, list[str]]:
    remaining = list(tokens)
    project: str | None = None
    while remaining and remaining[0] == '--project':
        remaining.pop(0)
        if not remaining:
            raise error_type('--project requires a path')
        project = remaining.pop(0)
    return project, remaining


def parse_start(tokens: list[str], *, project: str | None, error_type) -> ParsedStartCommand:
    parser = argparse.ArgumentParser(prog='ccb', add_help=False)
    parser.add_argument('-s', '--safe', action='store_true')
    parser.add_argument('-n', '--new-context', dest='reset_context', action='store_true')
    try:
        namespace, extra = parser.parse_known_args(tokens)
    except SystemExit as exc:
        raise error_type('invalid start command') from exc
    if extra:
        if any(token in _REMOVED_START_FLAGS for token in extra):
            raise error_type('`-a` and `-r` are no longer supported; use `ccb`, `ccb -s`, or `ccb -n`')
        if any(str(token).startswith('-') for token in extra):
            raise error_type('invalid start command')
        raise error_type(
            'start does not accept agent names or extra arguments; '
            'configure startup agents in `.ccb/ccb.config` and run `ccb`'
        )
    return ParsedStartCommand(
        project=project,
        agent_names=(),
        restore=not bool(namespace.reset_context),
        auto_permission=not bool(namespace.safe),
        reset_context=bool(namespace.reset_context),
    )


__all__ = ['parse_global_options', 'parse_start']
