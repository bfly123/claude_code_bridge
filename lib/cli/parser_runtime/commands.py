from __future__ import annotations

import argparse

from cli.models import (
    ParsedAckCommand,
    ParsedCancelCommand,
    ParsedConfigValidateCommand,
    ParsedDoctorCommand,
    ParsedInboxCommand,
    ParsedKillCommand,
    ParsedLogsCommand,
    ParsedOpenCommand,
    ParsedPendCommand,
    ParsedPingCommand,
    ParsedPsCommand,
    ParsedQueueCommand,
    ParsedResubmitCommand,
    ParsedRetryCommand,
    ParsedTraceCommand,
    ParsedWaitCommand,
    ParsedWatchCommand,
)

from .common import parse_args, require_no_extra
from .constants import WAIT_COMMAND_TO_MODE


def parse_cancel(tokens: list[str], *, project: str | None, error_type) -> ParsedCancelCommand:
    if len(tokens) != 1:
        raise error_type('cancel requires <job_id>')
    return ParsedCancelCommand(project=project, job_id=tokens[0])


def parse_kill(tokens: list[str], *, project: str | None, error_type) -> ParsedKillCommand:
    parser = argparse.ArgumentParser(prog='ccb kill', add_help=False)
    parser.add_argument('-f', '--force', action='store_true')
    namespace = parse_args(parser, tokens, error_message='invalid kill command', error_type=error_type)
    return ParsedKillCommand(project=project, force=bool(namespace.force))


def parse_open(tokens: list[str], *, project: str | None, error_type) -> ParsedOpenCommand:
    require_no_extra(tokens, command='open', error_type=error_type)
    return ParsedOpenCommand(project=project)


def parse_ps(tokens: list[str], *, project: str | None, error_type) -> ParsedPsCommand:
    parser = argparse.ArgumentParser(prog='ccb ps', add_help=False)
    parser.add_argument('--alive', action='store_true')
    namespace = parse_args(parser, tokens, error_message='invalid ps command', error_type=error_type)
    return ParsedPsCommand(project=project, alive_only=bool(namespace.alive))


def parse_ping(tokens: list[str], *, project: str | None, error_type) -> ParsedPingCommand:
    if len(tokens) != 1:
        raise error_type('ping requires <agent_name|all>')
    return ParsedPingCommand(project=project, target=tokens[0])


def parse_watch(tokens: list[str], *, project: str | None, error_type) -> ParsedWatchCommand:
    if len(tokens) != 1:
        raise error_type('watch requires <agent_name|job_id>')
    return ParsedWatchCommand(project=project, target=tokens[0])


def parse_pend(tokens: list[str], *, project: str | None, error_type) -> ParsedPendCommand:
    if not tokens or len(tokens) > 2:
        raise error_type('pend requires <agent_name|job_id> [N]')
    count: int | None = None
    if len(tokens) == 2:
        try:
            count = int(tokens[1])
        except ValueError as exc:
            raise error_type('pend count must be an integer') from exc
        if count <= 0:
            raise error_type('pend count must be positive')
    return ParsedPendCommand(project=project, target=tokens[0], count=count)


def parse_queue(tokens: list[str], *, project: str | None, error_type) -> ParsedQueueCommand:
    if len(tokens) != 1:
        raise error_type('queue requires <agent_name|all>')
    return ParsedQueueCommand(project=project, target=tokens[0])


def parse_trace(tokens: list[str], *, project: str | None, error_type) -> ParsedTraceCommand:
    if len(tokens) != 1:
        raise error_type('trace requires <submission_id|message_id|attempt_id|reply_id|job_id>')
    return ParsedTraceCommand(project=project, target=tokens[0])


def parse_resubmit(tokens: list[str], *, project: str | None, error_type) -> ParsedResubmitCommand:
    if len(tokens) != 1:
        raise error_type('resubmit requires <message_id>')
    return ParsedResubmitCommand(project=project, message_id=tokens[0])


def parse_retry(tokens: list[str], *, project: str | None, error_type) -> ParsedRetryCommand:
    if len(tokens) != 1:
        raise error_type('retry requires <job_id|attempt_id>')
    return ParsedRetryCommand(project=project, target=tokens[0])


def parse_wait(command_name: str, tokens: list[str], *, project: str | None, error_type) -> ParsedWaitCommand:
    parser = argparse.ArgumentParser(prog=f'ccb {command_name}', add_help=False)
    parser.add_argument('--timeout', type=float, default=None)
    if command_name == 'wait-quorum':
        parser.add_argument('quorum', type=int)
        parser.add_argument('target')
    else:
        parser.add_argument('target')
    namespace = parse_args(parser, tokens, error_message=f'invalid {command_name} command', error_type=error_type)
    timeout_s = float(namespace.timeout) if namespace.timeout is not None else None
    if timeout_s is not None and timeout_s <= 0:
        raise error_type('wait timeout must be positive')
    quorum = int(namespace.quorum) if getattr(namespace, 'quorum', None) is not None else None
    if quorum is not None and quorum <= 0:
        raise error_type('wait quorum must be positive')
    return ParsedWaitCommand(
        project=project,
        mode=WAIT_COMMAND_TO_MODE[command_name],
        target=str(namespace.target),
        quorum=quorum,
        timeout_s=timeout_s,
    )


def parse_inbox(tokens: list[str], *, project: str | None, error_type) -> ParsedInboxCommand:
    if len(tokens) != 1:
        raise error_type('inbox requires <agent_name>')
    return ParsedInboxCommand(project=project, agent_name=tokens[0])


def parse_ack(tokens: list[str], *, project: str | None, error_type) -> ParsedAckCommand:
    if not tokens or len(tokens) > 2:
        raise error_type('ack requires <agent_name> [inbound_event_id]')
    inbound_event_id = tokens[1] if len(tokens) == 2 else None
    return ParsedAckCommand(project=project, agent_name=tokens[0], inbound_event_id=inbound_event_id)


def parse_logs(tokens: list[str], *, project: str | None, error_type) -> ParsedLogsCommand:
    if len(tokens) != 1:
        raise error_type('logs requires <agent_name>')
    return ParsedLogsCommand(project=project, agent_name=tokens[0])


def parse_doctor(tokens: list[str], *, project: str | None, error_type) -> ParsedDoctorCommand:
    parser = argparse.ArgumentParser(prog='ccb doctor', add_help=False)
    parser.add_argument('--bundle', action='store_true')
    parser.add_argument('--output', dest='output_path', default=None)
    namespace = parse_args(parser, tokens, error_message='invalid doctor command', error_type=error_type)
    bundle = bool(namespace.bundle or namespace.output_path)
    return ParsedDoctorCommand(project=project, bundle=bundle, output_path=namespace.output_path)


def parse_config(tokens: list[str], *, project: str | None, error_type) -> ParsedConfigValidateCommand:
    if tokens != ['validate']:
        raise error_type('config only supports: ccb config validate')
    return ParsedConfigValidateCommand(project=project)


__all__ = [
    'parse_ack',
    'parse_cancel',
    'parse_config',
    'parse_doctor',
    'parse_inbox',
    'parse_kill',
    'parse_logs',
    'parse_open',
    'parse_pend',
    'parse_ping',
    'parse_ps',
    'parse_queue',
    'parse_resubmit',
    'parse_retry',
    'parse_trace',
    'parse_wait',
    'parse_watch',
]
