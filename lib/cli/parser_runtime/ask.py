from __future__ import annotations

from cli.ask_syntax import parse_ask_route
from cli.models import ParsedAskCommand, ParsedAskWaitCommand, ParsedCancelCommand, ParsedPendCommand

from .constants import ASK_FLAG_OPTIONS, ASK_JOB_ACTIONS, ASK_OPTIONS_WITH_VALUES

_REMOVED_ASK_FLAGS = {
    '--sync': 'use `--wait`',
    '--async': 'omit the flag; async submit is already the default',
    '-o': 'use `--output`',
    '-t': 'use `--timeout`',
}


def _parse_job_action(tokens: list[str], *, project: str | None, error_type):
    if not tokens or tokens[0] not in ASK_JOB_ACTIONS:
        return None
    action = tokens[0]
    if len(tokens) != 2:
        raise error_type(f'ask {action} requires <job_id>')
    if action == 'wait':
        return ParsedAskWaitCommand(project=project, job_id=tokens[1])
    if action == 'get':
        return ParsedPendCommand(project=project, target=tokens[1], count=None)
    return ParsedCancelCommand(project=project, job_id=tokens[1])


def _default_options() -> dict[str, str | float | None]:
    return {
        'task_id': None,
        'reply_to': None,
        'mode': None,
        'output_path': None,
        'timeout_s': None,
    }


def _set_option_value(options: dict[str, str | float | None], option: str, value: str, *, error_type) -> None:
    if option == '--output':
        options['output_path'] = value
        return
    if option == '--timeout':
        try:
            options['timeout_s'] = float(value)
        except ValueError as exc:
            raise error_type(f'invalid {option}: {exc}') from exc
        return
    options[option[2:].replace('-', '_')] = value


def _parse_route_options(remaining: list[str], *, error_type):
    options = _default_options()
    silence = False
    wait = False
    while remaining and remaining[0].startswith('-'):
        option = remaining.pop(0)
        if option in _REMOVED_ASK_FLAGS:
            raise error_type(f'{option} is no longer supported; {_REMOVED_ASK_FLAGS[option]}')
        if option in ASK_FLAG_OPTIONS:
            if option == '--silence':
                silence = True
                continue
            if option == '--wait':
                wait = True
                continue
        if option not in ASK_OPTIONS_WITH_VALUES:
            raise error_type(f'unknown ask option: {option}')
        if not remaining:
            raise error_type(f'{option} requires a value')
        _set_option_value(options, option, remaining.pop(0), error_type=error_type)
    return options, silence, wait


def _validate_wait_options(*, route, options: dict[str, str | float | None], wait: bool, error_type) -> None:
    if options['output_path'] is not None and not wait:
        raise error_type('--output requires --wait')
    if wait and route.target == 'all':
        raise error_type('ccb ask --wait requires a single target; broadcast is not supported')


def parse_ask(
    tokens: list[str],
    *,
    project: str | None,
    read_optional_stdin,
    error_type,
) -> ParsedAskCommand | ParsedAskWaitCommand | ParsedPendCommand | ParsedCancelCommand:
    action_command = _parse_job_action(tokens, project=project, error_type=error_type)
    if action_command is not None:
        return action_command

    remaining = list(tokens)
    options, silence, wait = _parse_route_options(remaining, error_type=error_type)

    stdin_text = read_optional_stdin()
    if stdin_text:
        remaining.append(stdin_text)

    try:
        route = parse_ask_route(remaining, command_name='ccb ask')
    except ValueError as exc:
        raise error_type(str(exc)) from exc
    _validate_wait_options(route=route, options=options, wait=wait, error_type=error_type)
    return ParsedAskCommand(
        project=project,
        target=route.target,
        sender=route.sender,
        message=route.message,
        task_id=options['task_id'],
        reply_to=options['reply_to'],
        mode=options['mode'],
        silence=silence,
        wait=wait,
        output_path=str(options['output_path']) if options['output_path'] is not None else None,
        timeout_s=float(options['timeout_s']) if options['timeout_s'] is not None else None,
    )


__all__ = ['parse_ask']
