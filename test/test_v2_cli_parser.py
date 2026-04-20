from __future__ import annotations

import io
import sys

import pytest

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
    ParsedPendCommand,
    ParsedPsCommand,
    ParsedQueueCommand,
    ParsedResubmitCommand,
    ParsedRetryCommand,
    ParsedStartCommand,
    ParsedTraceCommand,
    ParsedWaitCommand,
)
from cli.parser import CliParser, CliUsageError


@pytest.fixture()
def parser() -> CliParser:
    return CliParser()


def test_parse_start_defaults(parser: CliParser) -> None:
    parsed = parser.parse([])
    assert parsed == ParsedStartCommand(project=None, agent_names=(), restore=True, auto_permission=True)


def test_parse_start_with_project_and_flags(parser: CliParser) -> None:
    parsed = parser.parse(['--project', '/tmp/demo', '-s'])
    assert parsed == ParsedStartCommand(
        project='/tmp/demo',
        agent_names=(),
        restore=True,
        auto_permission=False,
    )


def test_parse_start_rejects_removed_restore_flag(parser: CliParser) -> None:
    with pytest.raises(CliUsageError, match='no longer supported'):
        parser.parse(['-r'])


def test_parse_start_rejects_removed_auto_flag(parser: CliParser) -> None:
    with pytest.raises(CliUsageError, match='no longer supported'):
        parser.parse(['-a'])


def test_parse_start_with_safe_flag(parser: CliParser) -> None:
    parsed = parser.parse(['-s'])
    assert parsed == ParsedStartCommand(
        project=None,
        agent_names=(),
        restore=True,
        auto_permission=False,
    )


def test_parse_start_with_new_context_flag(parser: CliParser) -> None:
    parsed = parser.parse(['-n'])
    assert parsed == ParsedStartCommand(
        project=None,
        agent_names=(),
        restore=False,
        auto_permission=True,
        reset_context=True,
    )


def test_parse_start_with_new_context_and_safe_flag(parser: CliParser) -> None:
    parsed = parser.parse(['-n', '-s'])
    assert parsed == ParsedStartCommand(
        project=None,
        agent_names=(),
        restore=False,
        auto_permission=False,
        reset_context=True,
    )


def test_parse_start_rejects_unknown_start_flag(parser: CliParser) -> None:
    with pytest.raises(CliUsageError, match='invalid start command'):
        parser.parse(['--bogus'])


def test_parse_start_rejects_manual_agent_selection(parser: CliParser) -> None:
    with pytest.raises(CliUsageError, match='configure startup agents in `.ccb/ccb.config`'):
        parser.parse(['agent1'])


def test_parse_ask_simple(parser: CliParser) -> None:
    parsed = parser.parse(['ask', 'agent1', 'continue', 'schema'])
    assert parsed == ParsedAskCommand(
        project=None,
        target='agent1',
        sender=None,
        message='continue schema',
    )


def test_parse_ask_explicit_sender(parser: CliParser) -> None:
    parsed = parser.parse(['ask', 'agent1', 'from', 'agent2', 'continue', 'schema'])
    assert parsed == ParsedAskCommand(
        project=None,
        target='agent1',
        sender='agent2',
        message='continue schema',
    )


def test_parse_ask_reads_message_from_stdin(parser: CliParser, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'stdin', io.StringIO('continue schema\n'))
    parsed = parser.parse(['ask', 'agent1'])
    assert parsed == ParsedAskCommand(
        project=None,
        target='agent1',
        sender=None,
        message='continue schema',
    )


def test_parse_ask_extended_form(parser: CliParser) -> None:
    parsed = parser.parse(
        [
            '--project',
            '/tmp/demo',
            'ask',
            '--task-id',
            'task-1',
            '--reply-to',
            'job-9',
            '--mode',
            'notify',
            'all',
            'from',
            'system',
            '--',
            'prepare',
            'regression',
        ]
    )
    assert parsed == ParsedAskCommand(
        project='/tmp/demo',
        target='all',
        sender='system',
        message='prepare regression',
        task_id='task-1',
        reply_to='job-9',
        mode='notify',
    )


def test_parse_ask_with_silence_flag(parser: CliParser) -> None:
    parsed = parser.parse(['ask', '--silence', 'agent1', 'from', 'agent2', 'ship', 'it'])
    assert parsed == ParsedAskCommand(
        project=None,
        target='agent1',
        sender='agent2',
        message='ship it',
        silence=True,
    )


def test_parse_ask_wait_submit_with_output_and_timeout(parser: CliParser) -> None:
    parsed = parser.parse(['ask', '--wait', '--output', '/tmp/reply.txt', '--timeout', '30', 'agent1', 'ship', 'it'])
    assert parsed == ParsedAskCommand(
        project=None,
        target='agent1',
        sender=None,
        message='ship it',
        wait=True,
        output_path='/tmp/reply.txt',
        timeout_s=30.0,
    )


@pytest.mark.parametrize(
    ('argv', 'message'),
    [
        (['ask', '--sync', 'agent1', 'ship', 'it'], '--sync is no longer supported'),
        (['ask', '--async', 'agent1', 'ship', 'it'], '--async is no longer supported'),
        (['ask', '-o', '/tmp/reply.txt', 'agent1', 'ship', 'it'], '-o is no longer supported'),
        (['ask', '-t', '30', 'agent1', 'ship', 'it'], '-t is no longer supported'),
    ],
)
def test_parse_ask_rejects_removed_alias_flags(parser: CliParser, argv: list[str], message: str) -> None:
    with pytest.raises(CliUsageError, match=message):
        parser.parse(argv)


def test_parse_ask_wait_get_and_cancel_subcommands(parser: CliParser) -> None:
    assert parser.parse(['ask', 'wait', 'job_123']) == ParsedAskWaitCommand(project=None, job_id='job_123')
    assert parser.parse(['ask', 'get', 'job_123']) == ParsedPendCommand(project=None, target='job_123', count=None)
    assert parser.parse(['ask', 'cancel', 'job_123']) == ParsedCancelCommand(project=None, job_id='job_123')


@pytest.mark.parametrize(
    'argv',
    [
        ['ask', 'agent1', 'from'],
        ['ask', 'agent1', 'from', 'agent2'],
        ['ask', '--unknown', 'agent1', 'from', 'user', 'x'],
        ['ask', '--output', '/tmp/reply.txt', 'agent1', 'x'],
        ['ask', '--wait', 'all', 'x'],
    ],
)
def test_parse_ask_invalid(parser: CliParser, argv: list[str]) -> None:
    with pytest.raises(CliUsageError):
        parser.parse(argv)


def test_parse_kill(parser: CliParser) -> None:
    assert parser.parse(['kill']) == ParsedKillCommand(project=None, force=False)
    assert parser.parse(['kill', '-f']) == ParsedKillCommand(project=None, force=True)


def test_parse_removed_attach_command_is_not_active(parser: CliParser) -> None:
    with pytest.raises(CliUsageError, match='start does not accept'):
        parser.parse(['open'])


def test_parse_ps_and_pend(parser: CliParser) -> None:
    assert parser.parse(['ps']) == ParsedPsCommand(project=None)
    assert parser.parse(['pend', 'job_123', '5']) == ParsedPendCommand(project=None, target='job_123', count=5)
    assert parser.parse(['queue', 'all']) == ParsedQueueCommand(project=None, target='all')


def test_parse_trace(parser: CliParser) -> None:
    assert parser.parse(['trace', 'job_123']) == ParsedTraceCommand(project=None, target='job_123')
    assert parser.parse(['resubmit', 'msg_123']) == ParsedResubmitCommand(project=None, message_id='msg_123')
    assert parser.parse(['retry', 'att_123']) == ParsedRetryCommand(project=None, target='att_123')
    assert parser.parse(['wait-any', 'msg_123']) == ParsedWaitCommand(
        project=None,
        mode='any',
        target='msg_123',
        quorum=None,
        timeout_s=None,
    )
    assert parser.parse(['wait-all', '--timeout', '5', 'sub_123']) == ParsedWaitCommand(
        project=None,
        mode='all',
        target='sub_123',
        quorum=None,
        timeout_s=5.0,
    )
    assert parser.parse(['wait-quorum', '2', 'sub_123']) == ParsedWaitCommand(
        project=None,
        mode='quorum',
        target='sub_123',
        quorum=2,
        timeout_s=None,
    )
    assert parser.parse(['inbox', 'agent1']) == ParsedInboxCommand(project=None, agent_name='agent1')
    assert parser.parse(['ack', 'agent1']) == ParsedAckCommand(project=None, agent_name='agent1')
    assert parser.parse(['ack', 'agent1', 'iev_123']) == ParsedAckCommand(
        project=None,
        agent_name='agent1',
        inbound_event_id='iev_123',
    )


def test_parse_logs(parser: CliParser) -> None:
    assert parser.parse(['logs', 'agent1']) == ParsedLogsCommand(project=None, agent_name='agent1')


def test_parse_doctor_bundle(parser: CliParser) -> None:
    assert parser.parse(['doctor']) == ParsedDoctorCommand(project=None, bundle=False, output_path=None)
    assert parser.parse(['doctor', '--output']) == ParsedDoctorCommand(project=None, bundle=True, output_path=None)
    assert parser.parse(['doctor', '--output', '/tmp/support.tar.gz']) == ParsedDoctorCommand(
        project=None,
        bundle=True,
        output_path='/tmp/support.tar.gz',
    )
    with pytest.raises(CliUsageError, match='doctor --bundle'):
        parser.parse(['doctor', '--bundle'])


def test_parse_config_validate(parser: CliParser) -> None:
    assert parser.parse(['config', 'validate']) == ParsedConfigValidateCommand(project=None)


def test_parse_config_validate_rejects_extra_args(parser: CliParser) -> None:
    with pytest.raises(CliUsageError):
        parser.parse(['config', 'validate', 'extra'])


def test_parse_fault_commands(parser: CliParser) -> None:
    assert parser.parse(['fault', 'list']) == ParsedFaultListCommand(project=None)
    assert parser.parse(
        ['fault', 'arm', 'agent2', '--task-id', 'drill-1', '--reason', 'transport_error', '--count', '3', '--error', 'drill']
    ) == ParsedFaultArmCommand(
        project=None,
        agent_name='agent2',
        task_id='drill-1',
        reason='transport_error',
        count=3,
        error_message='drill',
    )
    assert parser.parse(['fault', 'clear', 'all']) == ParsedFaultClearCommand(project=None, target='all')


def test_parse_fault_rejects_invalid_forms(parser: CliParser) -> None:
    with pytest.raises(CliUsageError):
        parser.parse(['fault'])
    with pytest.raises(CliUsageError):
        parser.parse(['fault', 'arm', 'agent2'])
    with pytest.raises(CliUsageError):
        parser.parse(['fault', 'clear'])
