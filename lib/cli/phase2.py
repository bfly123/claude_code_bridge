from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence, TextIO

from agents.config_loader import ConfigValidationError, ensure_bootstrap_project_config
from cli.context import CliContextBuilder
from cli.models import (
    ParsedAckCommand,
    ParsedAskCommand,
    ParsedAskWaitCommand,
    ParsedCancelCommand,
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
)
from cli.parser import CliParser, CliUsageError
from cli.render import (
    render_ack,
    render_ask,
    render_cancel,
    render_config_validate,
    render_doctor_bundle,
    render_doctor,
    render_fault_arm,
    render_fault_clear,
    render_fault_list,
    render_inbox,
    render_kill,
    render_logs,
    render_mapping,
    render_open,
    render_pend,
    render_ps,
    render_queue,
    render_resubmit,
    render_retry,
    render_start,
    render_trace,
    render_wait,
    render_watch_batch,
    write_lines,
)
from cli.services.ack import ack_reply
from cli.services.ask import exit_code_for_ask_status, submit_ask, watch_ask_job, write_ask_output
from cli.services.cancel import cancel_job
from cli.services.config_validate import validate_config_context
from cli.services.doctor import doctor_summary
from cli.services.diagnostics import export_diagnostic_bundle
from cli.services.fault import arm_fault_rule, clear_fault_rule, list_fault_rules
from cli.services.inbox import inbox_target
from cli.services.kill import kill_project
from cli.services.logs import agent_logs
from cli.services.open import open_project
from cli.services.pend import pend_target
from cli.services.ping import ping_target
from cli.services.ps import ps_summary
from cli.services.queue import queue_target
from cli.services.reset_project import reset_project_state
from cli.services.resubmit import resubmit_message
from cli.services.retry import retry_attempt
from cli.services.start import start_agents
from cli.services.trace import trace_target
from cli.services.wait import wait_for_replies
from cli.services.watch import watch_target
from project.discovery import ProjectDiscoveryError


def maybe_handle_phase2(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    config_command = _looks_like_config_validate(argv)
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    try:
        command = CliParser().parse(list(argv))
    except CliUsageError as exc:
        prefix = 'config_status: invalid' if config_command else 'command_status: invalid'
        print(f'{prefix}\nerror: {exc}', file=err)
        return 2

    try:
        context = _build_context(command, cwd=cwd, out=out)
        if command.kind != 'config-validate':
            ensure_bootstrap_project_config(context.project.project_root)
        code = _dispatch(context, command, out)
    except ProjectDiscoveryError as exc:
        prefix = 'config_status: invalid' if command.kind == 'config-validate' else 'command_status: failed'
        print(f'{prefix}\nerror: {exc}', file=err)
        return 2 if command.kind == 'config-validate' else 1
    except (ConfigValidationError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        prefix = 'config_status: invalid' if command.kind == 'config-validate' else 'command_status: failed'
        print(f'{prefix}\nerror: {exc}', file=err)
        return 1
    return code


def _build_context(command, *, cwd: Path | None, out: TextIO):
    if isinstance(command, ParsedStartCommand) and command.reset_context:
        return _build_reset_start_context(command, cwd=cwd, out=out)
    return CliContextBuilder().build(
        command,
        cwd=cwd,
        bootstrap_if_missing=command.kind != 'config-validate',
    )


def _build_reset_start_context(command: ParsedStartCommand, *, cwd: Path | None, out: TextIO):
    current = Path(cwd or Path.cwd()).expanduser()
    try:
        current = current.resolve()
    except Exception:
        current = current.absolute()

    existing_context = _resolve_existing_context(command, cwd=current)
    project_root = (
        existing_context.project.project_root
        if existing_context is not None
        else _resolve_requested_project_root(command, cwd=current)
    )
    _confirm_project_reset(project_root, out=out)
    reset_project_state(project_root, context=existing_context)
    return CliContextBuilder().build(
        command,
        cwd=current,
        bootstrap_if_missing=True,
    )


def _resolve_existing_context(command: ParsedStartCommand, *, cwd: Path):
    try:
        return CliContextBuilder().build(
            command,
            cwd=cwd,
            bootstrap_if_missing=False,
        )
    except ProjectDiscoveryError:
        return None


def _resolve_requested_project_root(command: ParsedStartCommand, *, cwd: Path) -> Path:
    root = Path(command.project).expanduser() if command.project else cwd
    try:
        root = root.resolve()
    except Exception:
        root = root.absolute()
    if not root.exists() or not root.is_dir():
        raise ProjectDiscoveryError(f'project root not found: {root}')
    return root


def _confirm_project_reset(project_root: Path, *, out: TextIO) -> None:
    if not _stream_is_tty(sys.stdin):
        raise RuntimeError('ccb -n requires interactive confirmation on stdin')
    print(
        f'Refresh project memory/context under {project_root / ".ccb"}? [y/N] ',
        end='',
        file=out,
        flush=True,
    )
    reply = sys.stdin.readline()
    if str(reply or '').strip().lower() not in {'y', 'yes'}:
        raise RuntimeError('project reset cancelled')


def _dispatch(context, command, out: TextIO) -> int:
    if command.kind == 'config-validate':
        summary = validate_config_context(context)
        write_lines(out, render_config_validate(summary))
        return 0
    if isinstance(command, ParsedStartCommand):
        summary = start_agents(context, command)
        if _should_auto_open_after_start(command, out=out):
            open_summary = open_project(context, ParsedOpenCommand(project=command.project))
            write_lines(out, render_open(open_summary))
            return 0
        write_lines(out, render_start(summary))
        return 0
    if isinstance(command, ParsedAskCommand):
        summary = submit_ask(context, command)
        if not command.wait:
            write_lines(out, render_ask(summary))
            return 0
        if len(summary.jobs) != 1:
            raise RuntimeError('ccb ask --wait requires exactly one accepted job')
        terminal = watch_ask_job(
            context,
            summary.jobs[0]['job_id'],
            out,
            timeout=command.timeout_s,
            emit_output=command.output_path is None,
        )
        reply = terminal.reply or ''
        if command.output_path is not None:
            write_ask_output(command.output_path, reply)
        return exit_code_for_ask_status(terminal.status, reply=reply)
    if isinstance(command, ParsedAskWaitCommand):
        terminal = watch_ask_job(context, command.job_id, out, timeout=command.timeout_s, emit_output=True)
        return exit_code_for_ask_status(terminal.status, reply=terminal.reply or '')
    if isinstance(command, ParsedPingCommand):
        payload = ping_target(context, command)
        write_lines(out, render_mapping(payload))
        return 0
    if isinstance(command, ParsedPendCommand):
        payload = pend_target(context, command)
        write_lines(out, render_pend(payload))
        return 0
    if isinstance(command, ParsedQueueCommand):
        payload = queue_target(context, command)
        write_lines(out, render_queue(payload))
        return 0
    if isinstance(command, ParsedTraceCommand):
        payload = trace_target(context, command)
        write_lines(out, render_trace(payload))
        return 0
    if isinstance(command, ParsedResubmitCommand):
        summary = resubmit_message(context, command)
        write_lines(out, render_resubmit(summary))
        return 0
    if isinstance(command, ParsedRetryCommand):
        summary = retry_attempt(context, command)
        write_lines(out, render_retry(summary))
        return 0
    if isinstance(command, ParsedWaitCommand):
        summary = wait_for_replies(context, command)
        write_lines(out, render_wait(summary))
        return 0
    if isinstance(command, ParsedInboxCommand):
        payload = inbox_target(context, command)
        write_lines(out, render_inbox(payload))
        return 0
    if isinstance(command, ParsedAckCommand):
        payload = ack_reply(context, command)
        write_lines(out, render_ack(payload))
        return 0
    if isinstance(command, ParsedWatchCommand):
        for batch in watch_target(context, command):
            write_lines(out, render_watch_batch(batch))
        return 0
    if isinstance(command, ParsedCancelCommand):
        payload = cancel_job(context, command)
        write_lines(out, render_cancel(payload))
        return 0
    if isinstance(command, ParsedKillCommand):
        summary = kill_project(context, command)
        write_lines(out, render_kill(summary))
        return 0
    if isinstance(command, ParsedOpenCommand):
        summary = open_project(context, command)
        write_lines(out, render_open(summary))
        return 0
    if isinstance(command, ParsedLogsCommand):
        summary = agent_logs(context, command)
        write_lines(out, render_logs(summary))
        return 0
    if isinstance(command, ParsedPsCommand):
        payload = ps_summary(context, command)
        write_lines(out, render_ps(payload))
        return 0
    if isinstance(command, ParsedDoctorCommand):
        if command.bundle:
            summary = export_diagnostic_bundle(context, command)
            write_lines(out, render_doctor_bundle(summary))
            return 0
        payload = doctor_summary(context)
        write_lines(out, render_doctor(payload))
        return 0
    if isinstance(command, ParsedFaultListCommand):
        summary = list_fault_rules(context)
        write_lines(out, render_fault_list(summary))
        return 0
    if isinstance(command, ParsedFaultArmCommand):
        summary = arm_fault_rule(context, command)
        write_lines(out, render_fault_arm(summary))
        return 0
    if isinstance(command, ParsedFaultClearCommand):
        summary = clear_fault_rule(context, command)
        write_lines(out, render_fault_clear(summary))
        return 0
    print(f'command_status: unsupported\nerror: unsupported v2 command: {command.kind}', file=out)
    return 2


def _looks_like_config_validate(argv: Sequence[str]) -> bool:
    tokens = list(argv)
    index = 0
    while index < len(tokens) and tokens[index] == '--project':
        index += 2
    remaining = tokens[index:]
    return bool(remaining) and remaining[0] == 'config'


def _should_auto_open_after_start(command: ParsedStartCommand, *, out: TextIO) -> bool:
    del command
    if _env_truthy('CCB_NO_AUTO_OPEN'):
        return False
    return _stream_is_tty(sys.stdin) and _stream_is_tty(out)


def _stream_is_tty(stream: object) -> bool:
    checker = getattr(stream, 'isatty', None)
    if not callable(checker):
        return False
    try:
        return bool(checker())
    except Exception:
        return False


def _env_truthy(name: str) -> bool:
    value = str(os.environ.get(name) or '').strip().lower()
    return value in {'1', 'true', 'yes', 'on'}
