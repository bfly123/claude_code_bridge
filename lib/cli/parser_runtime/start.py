from __future__ import annotations

import argparse

from cli.models import ParsedStartCommand

from .common import parse_args


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
    parser.add_argument('agent_names', nargs='*')
    parser.add_argument('-r', '--restore', action='store_true')
    parser.add_argument('-a', '--auto', action='store_true')
    parser.add_argument('-n', '--new-context', dest='reset_context', action='store_true')
    namespace = parse_args(parser, tokens, error_message='invalid start command', error_type=error_type)
    return ParsedStartCommand(
        project=project,
        agent_names=tuple(namespace.agent_names),
        restore=not bool(namespace.reset_context),
        auto_permission=True,
        reset_context=bool(namespace.reset_context),
    )


__all__ = ['parse_global_options', 'parse_start']
