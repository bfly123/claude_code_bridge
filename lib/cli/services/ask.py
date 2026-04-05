from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TextIO
import time

from agents.config_loader import load_project_config
from ccbd.api_models import DeliveryScope, MessageEnvelope
from ccbd.socket_client import CcbdClientError
from cli.ask_usage import ask_wait_poll_interval_seconds, ask_wait_timeout_seconds
from cli.context import CliContext
from cli.ask_sender import resolve_ask_sender
from cli.output import EXIT_ERROR, EXIT_NO_REPLY, EXIT_OK, atomic_write_text
from cli.render import render_watch_batch, write_lines
from cli.models import ParsedAskCommand
from cli.services.watch import WatchEventBatch
from mailbox_targets import COMMAND_MAILBOX_ACTOR

from .daemon import CcbdServiceError, connect_mounted_daemon


@dataclass(frozen=True)
class AskSummary:
    project_id: str
    submission_id: str | None
    jobs: tuple[dict, ...]


def submit_ask(context: CliContext, command: ParsedAskCommand) -> AskSummary:
    config = load_project_config(context.project.project_root).config
    normalized_target = str(command.target or '').strip().lower()
    if normalized_target != 'all' and normalized_target not in config.agents:
        raise ValueError(f'unknown agent: {command.target}')
    sender = resolve_ask_sender(context, command.sender)
    normalized_sender = str(sender or '').strip().lower()
    if normalized_sender not in {'user', 'system', 'manual', COMMAND_MAILBOX_ACTOR} and normalized_sender not in config.agents:
        raise ValueError(f'unknown sender agent: {sender}')
    handle = connect_mounted_daemon(context, allow_restart_stale=True)
    assert handle.client is not None
    payload = handle.client.submit(
        MessageEnvelope(
            project_id=context.project.project_id,
            to_agent=normalized_target,
            from_actor=sender,
            body=command.message,
            task_id=command.task_id,
            reply_to=command.reply_to,
            message_type=command.mode or 'ask',
            delivery_scope=DeliveryScope.BROADCAST if command.target == 'all' else DeliveryScope.SINGLE,
            silence_on_success=command.silence,
        )
    )
    if 'job_id' in payload:
        jobs = (
            {
                'job_id': payload['job_id'],
                'agent_name': payload['agent_name'],
                'target_kind': payload.get('target_kind', 'agent'),
                'target_name': payload.get('target_name', payload['agent_name']),
                'provider_instance': payload.get('provider_instance'),
                'status': payload['status'],
            },
        )
        submission_id = None
    else:
        jobs = tuple(payload.get('jobs', []))
        submission_id = payload.get('submission_id')
    return AskSummary(project_id=context.project.project_id, submission_id=submission_id, jobs=jobs)


def watch_ask_job(
    context: CliContext,
    job_id: str,
    out: TextIO,
    *,
    timeout: float | None,
    emit_output: bool,
) -> WatchEventBatch:
    handle = connect_mounted_daemon(context, allow_restart_stale=True)
    assert handle.client is not None
    client = handle.client
    cursor = 0
    timeout_s = ask_wait_timeout_seconds() if timeout is None else float(timeout)
    deadline = None if timeout_s <= 0 else (time.monotonic() + timeout_s)
    poll_interval = ask_wait_poll_interval_seconds()

    while True:
        try:
            payload = client.watch(job_id, cursor=cursor)
        except (CcbdClientError, CcbdServiceError):
            if deadline is not None and time.monotonic() > deadline:
                raise RuntimeError(f'wait timed out for {job_id}')
            handle = connect_mounted_daemon(context, allow_restart_stale=True)
            assert handle.client is not None
            client = handle.client
            time.sleep(poll_interval)
            continue

        batch = WatchEventBatch(
            target=job_id,
            job_id=payload['job_id'],
            agent_name=payload.get('agent_name') or '',
            target_kind=payload.get('target_kind'),
            target_name=payload.get('target_name') or payload.get('agent_name') or '',
            provider=payload.get('provider'),
            provider_instance=payload.get('provider_instance'),
            cursor=int(payload['cursor']),
            generation=int(payload['generation']) if payload.get('generation') is not None else None,
            terminal=bool(payload['terminal']),
            status=payload.get('status'),
            reply=payload.get('reply') or '',
            events=tuple(payload.get('events', [])),
        )
        if emit_output and batch.events:
            write_lines(out, render_watch_batch(batch))
        cursor = batch.cursor
        if batch.terminal:
            if emit_output and not batch.events:
                write_lines(out, render_watch_batch(batch))
            return batch
        if deadline is not None and time.monotonic() > deadline:
            raise RuntimeError(f'wait timed out for {job_id}')
        time.sleep(poll_interval)


def exit_code_for_ask_status(status: str | None, *, reply: str) -> int:
    normalized = str(status or '').strip().lower()
    if normalized == 'completed':
        return EXIT_OK
    if normalized == 'incomplete':
        return EXIT_NO_REPLY if reply else EXIT_ERROR
    return EXIT_ERROR


def write_ask_output(path: str | Path, reply: str) -> None:
    content = reply + ('\n' if reply and not reply.endswith('\n') else '')
    atomic_write_text(Path(path), content)
