from __future__ import annotations

import argparse

from cli.models import ParsedFaultArmCommand, ParsedFaultClearCommand, ParsedFaultListCommand
from fault_injection import VALID_FAILURE_REASONS

from .common import parse_args, require_no_extra


def parse_fault(
    tokens: list[str],
    *,
    project: str | None,
    error_type,
) -> ParsedFaultListCommand | ParsedFaultArmCommand | ParsedFaultClearCommand:
    if not tokens:
        raise error_type('fault requires one of: list, arm, clear')
    action = tokens[0]
    rest = tokens[1:]
    if action == 'list':
        require_no_extra(rest, command='fault list', error_type=error_type)
        return ParsedFaultListCommand(project=project)
    if action == 'arm':
        parser = argparse.ArgumentParser(prog='ccb fault arm', add_help=False)
        parser.add_argument('agent_name')
        parser.add_argument('--task-id', required=True)
        parser.add_argument('--reason', choices=tuple(sorted(VALID_FAILURE_REASONS)), default='api_error')
        parser.add_argument('--count', type=int, default=1)
        parser.add_argument('--error', dest='error_message', default='fault injection drill')
        namespace = parse_args(parser, rest, error_message='invalid fault arm command', error_type=error_type)
        if int(namespace.count) <= 0:
            raise error_type('fault arm count must be positive')
        return ParsedFaultArmCommand(
            project=project,
            agent_name=str(namespace.agent_name),
            task_id=str(namespace.task_id),
            reason=str(namespace.reason),
            count=int(namespace.count),
            error_message=str(namespace.error_message),
        )
    if action == 'clear':
        if len(rest) != 1:
            raise error_type('fault clear requires <rule_id|all>')
        return ParsedFaultClearCommand(project=project, target=rest[0])
    raise error_type('fault requires one of: list, arm, clear')


__all__ = ['parse_fault']
