from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator
import os
import time

from ccbd.socket_client import CcbdClientError
from cli.context import CliContext
from cli.models import ParsedWatchCommand

from .daemon import CcbdServiceError, connect_mounted_daemon


@dataclass(frozen=True)
class WatchEventBatch:
    target: str
    job_id: str
    agent_name: str
    target_kind: str | None
    target_name: str
    provider: str | None
    provider_instance: str | None
    cursor: int
    generation: int | None
    terminal: bool
    status: str | None
    reply: str
    events: tuple[dict, ...]


_DEFAULT_POLL_INTERVAL_S = 0.1
_DEFAULT_TIMEOUT_S = 10.0


def watch_target(context: CliContext, command: ParsedWatchCommand) -> Iterator[WatchEventBatch]:
    handle = connect_mounted_daemon(context, allow_restart_stale=True)
    assert handle.client is not None
    cursor = 0
    deadline = time.time() + float(os.environ.get('CCB_WATCH_TIMEOUT_S', _DEFAULT_TIMEOUT_S))
    poll_interval = float(os.environ.get('CCB_WATCH_POLL_INTERVAL_S', _DEFAULT_POLL_INTERVAL_S))

    while True:
        try:
            payload = handle.client.watch(command.target, cursor=cursor)
        except (CcbdClientError, CcbdServiceError):
            if time.time() > deadline:
                raise RuntimeError(f'watch timed out for target {command.target}')
            handle = connect_mounted_daemon(context, allow_restart_stale=True)
            assert handle.client is not None
            time.sleep(poll_interval)
            continue
        batch = WatchEventBatch(
            target=command.target,
            job_id=payload['job_id'],
            agent_name=payload['agent_name'],
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
        if batch.events:
            yield batch
        cursor = batch.cursor
        if batch.terminal:
            if not batch.events:
                yield batch
            return
        if time.time() > deadline:
            raise RuntimeError(f'watch timed out for target {command.target}')
        time.sleep(poll_interval)
