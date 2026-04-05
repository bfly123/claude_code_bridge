from __future__ import annotations

import argparse
import sys
from typing import Iterable

from cli.ask_syntax import parse_ask_route
from compat import read_stdin_text
from cli.models import (
    ParsedAckCommand,
    ParsedAskCommand,
    ParsedAskWaitCommand,
    ParsedCancelCommand,
    ParsedConfigValidateCommand,
    ParsedDoctorCommand,
    ParsedFaultArmCommand,
    ParsedFaultClearCommand,
    ParsedFaultListCommand,
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
    ParsedStartCommand,
    ParsedTraceCommand,
    ParsedWaitCommand,
    ParsedWatchCommand,
    ParsedCommand,
)
from fault_injection import VALID_FAILURE_REASONS

SUBCOMMANDS = {
    'ask',
    'cancel',
    'kill',
    'open',
    'ps',
    'ping',
    'watch',
    'pend',
    'queue',
    'trace',
    'resubmit',
    'retry',
    'wait-any',
    'wait-all',
    'wait-quorum',
    'inbox',
    'ack',
    'logs',
    'doctor',
    'config',
    'fault',
}
ASK_OPTIONS_WITH_VALUES = {'--task-id', '--reply-to', '--mode', '--output', '-o', '--timeout', '-t'}
ASK_FLAG_OPTIONS = {'--silence', '--wait', '--sync', '--async'}
WAIT_COMMAND_TO_MODE = {
    'wait-any': 'any',
    'wait-all': 'all',
    'wait-quorum': 'quorum',
}
ASK_JOB_ACTIONS = {'wait', 'get', 'cancel'}


class CliUsageError(ValueError):
    pass


class CliParser:
    def parse(self, argv: Iterable[str]) -> ParsedCommand:
        tokens = list(argv)
        project, tokens = self._parse_global_options(tokens)
        if not tokens:
            return ParsedStartCommand(project=project, agent_names=(), restore=True, auto_permission=True)
        if tokens[0] not in SUBCOMMANDS:
            return self._parse_start(tokens, project=project)

        command = tokens[0]
        rest = tokens[1:]
        if command == 'ask':
            return self._parse_ask(rest, project=project)
        if command == 'cancel':
            return self._parse_cancel(rest, project=project)
        if command == 'kill':
            return self._parse_kill(rest, project=project)
        if command == 'open':
            return self._parse_open(rest, project=project)
        if command == 'ps':
            return self._parse_ps(rest, project=project)
        if command == 'ping':
            return self._parse_ping(rest, project=project)
        if command == 'watch':
            return self._parse_watch(rest, project=project)
        if command == 'pend':
            return self._parse_pend(rest, project=project)
        if command == 'queue':
            return self._parse_queue(rest, project=project)
        if command == 'trace':
            return self._parse_trace(rest, project=project)
        if command == 'resubmit':
            return self._parse_resubmit(rest, project=project)
        if command == 'retry':
            return self._parse_retry(rest, project=project)
        if command in WAIT_COMMAND_TO_MODE:
            return self._parse_wait(command, rest, project=project)
        if command == 'inbox':
            return self._parse_inbox(rest, project=project)
        if command == 'ack':
            return self._parse_ack(rest, project=project)
        if command == 'logs':
            return self._parse_logs(rest, project=project)
        if command == 'doctor':
            return self._parse_doctor(rest, project=project)
        if command == 'config':
            return self._parse_config(rest, project=project)
        if command == 'fault':
            return self._parse_fault(rest, project=project)
        raise CliUsageError(f'unknown command: {command}')

    def _parse_global_options(self, tokens: list[str]) -> tuple[str | None, list[str]]:
        remaining = list(tokens)
        project: str | None = None
        while remaining and remaining[0] == '--project':
            option = remaining.pop(0)
            if option == '--project':
                if not remaining:
                    raise CliUsageError('--project requires a path')
                project = remaining.pop(0)
                continue
        return project, remaining

    def _parse_start(self, tokens: list[str], *, project: str | None) -> ParsedStartCommand:
        parser = argparse.ArgumentParser(prog='ccb', add_help=False)
        parser.add_argument('agent_names', nargs='*')
        parser.add_argument('-r', '--restore', action='store_true')
        parser.add_argument('-a', '--auto', action='store_true')
        parser.add_argument('-n', '--new-context', dest='reset_context', action='store_true')
        try:
            namespace = parser.parse_args(tokens)
        except SystemExit as exc:
            raise CliUsageError('invalid start command') from exc
        return ParsedStartCommand(
            project=project,
            agent_names=tuple(namespace.agent_names),
            restore=not bool(namespace.reset_context),
            auto_permission=True,
            reset_context=bool(namespace.reset_context),
        )

    def _parse_ask(
        self,
        tokens: list[str],
        *,
        project: str | None,
    ) -> ParsedAskCommand | ParsedAskWaitCommand | ParsedPendCommand | ParsedCancelCommand:
        if tokens and tokens[0] in ASK_JOB_ACTIONS:
            action = tokens[0]
            if len(tokens) != 2:
                raise CliUsageError(f'ask {action} requires <job_id>')
            if action == 'wait':
                return ParsedAskWaitCommand(project=project, job_id=tokens[1])
            if action == 'get':
                return ParsedPendCommand(project=project, target=tokens[1], count=None)
            return ParsedCancelCommand(project=project, job_id=tokens[1])

        remaining = list(tokens)
        options: dict[str, str | float | None] = {
            'task_id': None,
            'reply_to': None,
            'mode': None,
            'output_path': None,
            'timeout_s': None,
        }
        silence = False
        wait = False
        async_mode = False
        while remaining and remaining[0].startswith('-'):
            option = remaining.pop(0)
            if option in ASK_FLAG_OPTIONS:
                if option == '--silence':
                    silence = True
                    continue
                if option in {'--wait', '--sync'}:
                    if async_mode:
                        raise CliUsageError('--async conflicts with --wait')
                    wait = True
                    continue
                if option == '--async':
                    if wait:
                        raise CliUsageError('--async conflicts with --wait')
                    async_mode = True
                    continue
            if option not in ASK_OPTIONS_WITH_VALUES:
                raise CliUsageError(f'unknown ask option: {option}')
            if not remaining:
                raise CliUsageError(f'{option} requires a value')
            value = remaining.pop(0)
            if option in {'--output', '-o'}:
                options['output_path'] = value
                continue
            if option in {'--timeout', '-t'}:
                try:
                    options['timeout_s'] = float(value)
                except ValueError as exc:
                    raise CliUsageError(f'invalid {option}: {exc}') from exc
                continue
            options[option[2:].replace('-', '_')] = value

        stdin_text = self._read_optional_stdin()
        if stdin_text:
            remaining.append(stdin_text)

        try:
            route = parse_ask_route(remaining, command_name='ccb ask')
        except ValueError as exc:
            raise CliUsageError(str(exc)) from exc
        if options['output_path'] is not None and not wait:
            raise CliUsageError('--output requires --wait')
        if wait and route.target == 'all':
            raise CliUsageError('ccb ask --wait requires a single target; broadcast is not supported')
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

    def _read_optional_stdin(self) -> str:
        if sys.stdin.isatty():
            return ''
        try:
            return read_stdin_text()
        except OSError:
            return ''

    def _require_no_extra(self, tokens: list[str], *, command: str) -> None:
        if tokens:
            raise CliUsageError(f'{command} does not accept extra arguments: {tokens}')

    def _parse_cancel(self, tokens: list[str], *, project: str | None) -> ParsedCancelCommand:
        if len(tokens) != 1:
            raise CliUsageError('cancel requires <job_id>')
        return ParsedCancelCommand(project=project, job_id=tokens[0])

    def _parse_kill(self, tokens: list[str], *, project: str | None) -> ParsedKillCommand:
        parser = argparse.ArgumentParser(prog='ccb kill', add_help=False)
        parser.add_argument('-f', '--force', action='store_true')
        try:
            namespace = parser.parse_args(tokens)
        except SystemExit as exc:
            raise CliUsageError('invalid kill command') from exc
        return ParsedKillCommand(project=project, force=bool(namespace.force))

    def _parse_open(self, tokens: list[str], *, project: str | None) -> ParsedOpenCommand:
        self._require_no_extra(tokens, command='open')
        return ParsedOpenCommand(project=project)

    def _parse_ps(self, tokens: list[str], *, project: str | None) -> ParsedPsCommand:
        parser = argparse.ArgumentParser(prog='ccb ps', add_help=False)
        parser.add_argument('--alive', action='store_true')
        try:
            namespace = parser.parse_args(tokens)
        except SystemExit as exc:
            raise CliUsageError('invalid ps command') from exc
        return ParsedPsCommand(project=project, alive_only=bool(namespace.alive))

    def _parse_ping(self, tokens: list[str], *, project: str | None) -> ParsedPingCommand:
        if len(tokens) != 1:
            raise CliUsageError('ping requires <agent_name|all>')
        return ParsedPingCommand(project=project, target=tokens[0])

    def _parse_watch(self, tokens: list[str], *, project: str | None) -> ParsedWatchCommand:
        if len(tokens) != 1:
            raise CliUsageError('watch requires <agent_name|job_id>')
        return ParsedWatchCommand(project=project, target=tokens[0])

    def _parse_pend(self, tokens: list[str], *, project: str | None) -> ParsedPendCommand:
        if not tokens or len(tokens) > 2:
            raise CliUsageError('pend requires <agent_name|job_id> [N]')
        count: int | None = None
        if len(tokens) == 2:
            try:
                count = int(tokens[1])
            except ValueError as exc:
                raise CliUsageError('pend count must be an integer') from exc
            if count <= 0:
                raise CliUsageError('pend count must be positive')
        return ParsedPendCommand(project=project, target=tokens[0], count=count)

    def _parse_queue(self, tokens: list[str], *, project: str | None) -> ParsedQueueCommand:
        if len(tokens) != 1:
            raise CliUsageError('queue requires <agent_name|all>')
        return ParsedQueueCommand(project=project, target=tokens[0])

    def _parse_trace(self, tokens: list[str], *, project: str | None) -> ParsedTraceCommand:
        if len(tokens) != 1:
            raise CliUsageError('trace requires <submission_id|message_id|attempt_id|reply_id|job_id>')
        return ParsedTraceCommand(project=project, target=tokens[0])

    def _parse_resubmit(self, tokens: list[str], *, project: str | None) -> ParsedResubmitCommand:
        if len(tokens) != 1:
            raise CliUsageError('resubmit requires <message_id>')
        return ParsedResubmitCommand(project=project, message_id=tokens[0])

    def _parse_retry(self, tokens: list[str], *, project: str | None) -> ParsedRetryCommand:
        if len(tokens) != 1:
            raise CliUsageError('retry requires <job_id|attempt_id>')
        return ParsedRetryCommand(project=project, target=tokens[0])

    def _parse_wait(self, command_name: str, tokens: list[str], *, project: str | None) -> ParsedWaitCommand:
        parser = argparse.ArgumentParser(prog=f'ccb {command_name}', add_help=False)
        parser.add_argument('--timeout', type=float, default=None)
        if command_name == 'wait-quorum':
            parser.add_argument('quorum', type=int)
            parser.add_argument('target')
        else:
            parser.add_argument('target')
        try:
            namespace = parser.parse_args(tokens)
        except SystemExit as exc:
            raise CliUsageError(f'invalid {command_name} command') from exc
        timeout_s = float(namespace.timeout) if namespace.timeout is not None else None
        if timeout_s is not None and timeout_s <= 0:
            raise CliUsageError('wait timeout must be positive')
        quorum = int(namespace.quorum) if getattr(namespace, 'quorum', None) is not None else None
        if quorum is not None and quorum <= 0:
            raise CliUsageError('wait quorum must be positive')
        return ParsedWaitCommand(
            project=project,
            mode=WAIT_COMMAND_TO_MODE[command_name],
            target=str(namespace.target),
            quorum=quorum,
            timeout_s=timeout_s,
        )

    def _parse_inbox(self, tokens: list[str], *, project: str | None) -> ParsedInboxCommand:
        if len(tokens) != 1:
            raise CliUsageError('inbox requires <agent_name>')
        return ParsedInboxCommand(project=project, agent_name=tokens[0])

    def _parse_ack(self, tokens: list[str], *, project: str | None) -> ParsedAckCommand:
        if not tokens or len(tokens) > 2:
            raise CliUsageError('ack requires <agent_name> [inbound_event_id]')
        inbound_event_id = tokens[1] if len(tokens) == 2 else None
        return ParsedAckCommand(project=project, agent_name=tokens[0], inbound_event_id=inbound_event_id)

    def _parse_logs(self, tokens: list[str], *, project: str | None) -> ParsedLogsCommand:
        if len(tokens) != 1:
            raise CliUsageError('logs requires <agent_name>')
        return ParsedLogsCommand(project=project, agent_name=tokens[0])

    def _parse_doctor(self, tokens: list[str], *, project: str | None) -> ParsedDoctorCommand:
        parser = argparse.ArgumentParser(prog='ccb doctor', add_help=False)
        parser.add_argument('--bundle', action='store_true')
        parser.add_argument('--output', dest='output_path', default=None)
        try:
            namespace = parser.parse_args(tokens)
        except SystemExit as exc:
            raise CliUsageError('invalid doctor command') from exc
        bundle = bool(namespace.bundle or namespace.output_path)
        return ParsedDoctorCommand(project=project, bundle=bundle, output_path=namespace.output_path)

    def _parse_config(self, tokens: list[str], *, project: str | None) -> ParsedConfigValidateCommand:
        if tokens != ['validate']:
            raise CliUsageError('config only supports: ccb config validate')
        return ParsedConfigValidateCommand(project=project)

    def _parse_fault(
        self,
        tokens: list[str],
        *,
        project: str | None,
    ) -> ParsedFaultListCommand | ParsedFaultArmCommand | ParsedFaultClearCommand:
        if not tokens:
            raise CliUsageError('fault requires one of: list, arm, clear')
        action = tokens[0]
        rest = tokens[1:]
        if action == 'list':
            self._require_no_extra(rest, command='fault list')
            return ParsedFaultListCommand(project=project)
        if action == 'arm':
            parser = argparse.ArgumentParser(prog='ccb fault arm', add_help=False)
            parser.add_argument('agent_name')
            parser.add_argument('--task-id', required=True)
            parser.add_argument('--reason', choices=tuple(sorted(VALID_FAILURE_REASONS)), default='api_error')
            parser.add_argument('--count', type=int, default=1)
            parser.add_argument('--error', dest='error_message', default='fault injection drill')
            try:
                namespace = parser.parse_args(rest)
            except SystemExit as exc:
                raise CliUsageError('invalid fault arm command') from exc
            if int(namespace.count) <= 0:
                raise CliUsageError('fault arm count must be positive')
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
                raise CliUsageError('fault clear requires <rule_id|all>')
            return ParsedFaultClearCommand(project=project, target=rest[0])
        raise CliUsageError('fault requires one of: list, arm, clear')
