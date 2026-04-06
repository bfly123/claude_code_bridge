from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Sequence, TextIO

from agents.config_loader import ConfigValidationError, ensure_bootstrap_project_config
from cli.context import CliContextBuilder
from cli.models import ParsedOpenCommand
from cli.parser import CliParser, CliUsageError
from cli.phase2_runtime import (
    build_context as _build_context_impl,
    confirm_project_reset as _confirm_project_reset_impl,
    dispatch as _dispatch_impl,
    looks_like_config_validate as _looks_like_config_validate_impl,
    should_auto_open_after_start as _should_auto_open_after_start_impl,
    stream_is_tty as _stream_is_tty_impl,
)
from cli.render import (
    render_ack,
    render_ask,
    render_cancel,
    render_config_validate,
    render_doctor,
    render_doctor_bundle,
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


def _error_prefix(*, kind: str, config_command: bool) -> str:
    if kind == 'invalid':
        return 'config_status: invalid' if config_command else 'command_status: invalid'
    return 'config_status: invalid' if config_command else 'command_status: failed'


def _print_phase2_error(err: TextIO, *, kind: str, config_command: bool, exc: Exception) -> None:
    print(f'{_error_prefix(kind=kind, config_command=config_command)}\nerror: {exc}', file=err)


def _parse_phase2_command(argv: Sequence[str], *, config_command: bool, err: TextIO):
    try:
        return CliParser().parse(list(argv))
    except CliUsageError as exc:
        _print_phase2_error(err, kind='invalid', config_command=config_command, exc=exc)
        return None


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
    command = _parse_phase2_command(argv, config_command=config_command, err=err)
    if command is None:
        return 2

    try:
        context = _build_context(command, cwd=cwd, out=out)
        if command.kind != 'config-validate':
            ensure_bootstrap_project_config(context.project.project_root)
        code = _dispatch(context, command, out)
    except ProjectDiscoveryError as exc:
        _print_phase2_error(
            err,
            kind='failed',
            config_command=command.kind == 'config-validate',
            exc=exc,
        )
        return 2 if command.kind == 'config-validate' else 1
    except (ConfigValidationError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        _print_phase2_error(
            err,
            kind='failed',
            config_command=command.kind == 'config-validate',
            exc=exc,
        )
        return 1
    return code


def _build_context(command, *, cwd: Path | None, out: TextIO):
    return _build_context_impl(
        command,
        cwd=cwd,
        out=out,
        builder_cls=CliContextBuilder,
        reset_project_state_fn=reset_project_state,
        project_discovery_error_cls=ProjectDiscoveryError,
        confirm_project_reset_fn=_confirm_project_reset,
    )


def _confirm_project_reset(project_root: Path, *, out: TextIO) -> None:
    _confirm_project_reset_impl(
        project_root,
        out=out,
        stdin=sys.stdin,
        stream_is_tty_fn=_stream_is_tty,
    )


def _dispatch(context, command, out: TextIO) -> int:
    return _dispatch_impl(context, command, out, _dispatch_services())


def _dispatch_services():
    return SimpleNamespace(
        ParsedOpenCommand=ParsedOpenCommand,
        ack_reply=ack_reply,
        agent_logs=agent_logs,
        arm_fault_rule=arm_fault_rule,
        cancel_job=cancel_job,
        clear_fault_rule=clear_fault_rule,
        doctor_summary=doctor_summary,
        exit_code_for_ask_status=exit_code_for_ask_status,
        export_diagnostic_bundle=export_diagnostic_bundle,
        inbox_target=inbox_target,
        kill_project=kill_project,
        list_fault_rules=list_fault_rules,
        open_project=open_project,
        pend_target=pend_target,
        ping_target=ping_target,
        ps_summary=ps_summary,
        queue_target=queue_target,
        render_ack=render_ack,
        render_ask=render_ask,
        render_cancel=render_cancel,
        render_config_validate=render_config_validate,
        render_doctor=render_doctor,
        render_doctor_bundle=render_doctor_bundle,
        render_fault_arm=render_fault_arm,
        render_fault_clear=render_fault_clear,
        render_fault_list=render_fault_list,
        render_inbox=render_inbox,
        render_kill=render_kill,
        render_logs=render_logs,
        render_mapping=render_mapping,
        render_open=render_open,
        render_pend=render_pend,
        render_ps=render_ps,
        render_queue=render_queue,
        render_resubmit=render_resubmit,
        render_retry=render_retry,
        render_start=render_start,
        render_trace=render_trace,
        render_wait=render_wait,
        render_watch_batch=render_watch_batch,
        resubmit_message=resubmit_message,
        retry_attempt=retry_attempt,
        should_auto_open_after_start=_should_auto_open_after_start,
        start_agents=start_agents,
        submit_ask=submit_ask,
        trace_target=trace_target,
        validate_config_context=validate_config_context,
        wait_for_replies=wait_for_replies,
        watch_ask_job=watch_ask_job,
        watch_target=watch_target,
        write_ask_output=write_ask_output,
        write_lines=write_lines,
    )


def _looks_like_config_validate(argv: Sequence[str]) -> bool:
    return _looks_like_config_validate_impl(argv)


def _should_auto_open_after_start(command, *, out: TextIO) -> bool:
    return _should_auto_open_after_start_impl(command, out=out, stdin=sys.stdin)


def _stream_is_tty(stream: object) -> bool:
    return _stream_is_tty_impl(stream)
