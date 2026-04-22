from __future__ import annotations

import time
from pathlib import Path
from typing import TextIO

from agents.config_loader import load_project_config
from ccbd.socket_client import CcbdClientError
from cli.ask_sender import resolve_ask_sender
from cli.ask_usage import ask_wait_poll_interval_seconds, ask_wait_timeout_seconds
from cli.render import render_watch_batch, write_lines

from .ask_runtime import AskSummary, exit_code_for_ask_status, write_ask_output
from .ask_runtime.submission import submit_ask as _submit_ask_impl
from .ask_runtime.watch import watch_ask_job as _watch_ask_job_impl
from .daemon import CcbdServiceError, connect_mounted_daemon, invoke_mounted_daemon


def submit_ask(context, command) -> AskSummary:
    return _submit_ask_impl(
        context,
        command,
        load_project_config_fn=load_project_config,
        resolve_ask_sender_fn=resolve_ask_sender,
        invoke_mounted_daemon_fn=invoke_mounted_daemon,
    )


def watch_ask_job(
    context,
    job_id: str,
    out: TextIO,
    *,
    timeout: float | None,
    emit_output: bool,
):
    return _watch_ask_job_impl(
        context,
        job_id,
        out,
        timeout=timeout,
        emit_output=emit_output,
        connect_mounted_daemon_fn=connect_mounted_daemon,
        reconnect_error_classes=(CcbdClientError, CcbdServiceError),
        monotonic_fn=time.monotonic,
        sleep_fn=time.sleep,
        poll_interval_seconds_fn=ask_wait_poll_interval_seconds,
        timeout_seconds_fn=ask_wait_timeout_seconds,
        render_watch_batch_fn=render_watch_batch,
        write_lines_fn=write_lines,
    )


__all__ = ['AskSummary', 'exit_code_for_ask_status', 'submit_ask', 'watch_ask_job', 'write_ask_output']
