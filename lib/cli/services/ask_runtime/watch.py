from __future__ import annotations

from collections.abc import Callable
from typing import TextIO

from cli.services.watch import WatchEventBatch


def watch_ask_job(
    context,
    job_id: str,
    out: TextIO,
    *,
    timeout: float | None,
    emit_output: bool,
    connect_mounted_daemon_fn: Callable,
    reconnect_error_classes: tuple[type[BaseException], ...],
    monotonic_fn: Callable[[], float],
    sleep_fn: Callable[[float], None],
    poll_interval_seconds_fn: Callable[[], float],
    timeout_seconds_fn: Callable[[], float],
    render_watch_batch_fn: Callable[[WatchEventBatch], tuple[str, ...]],
    write_lines_fn: Callable[[TextIO, tuple[str, ...]], None],
) -> WatchEventBatch:
    handle = connect_mounted_daemon_fn(context, allow_restart_stale=True)
    assert handle.client is not None
    client = handle.client
    cursor = 0
    deadline = _watch_deadline(timeout, timeout_seconds_fn=timeout_seconds_fn, monotonic_fn=monotonic_fn)
    poll_interval = poll_interval_seconds_fn()

    while True:
        try:
            payload = client.watch(job_id, cursor=cursor)
        except reconnect_error_classes:
            client = None
            while client is None:
                if _deadline_exceeded(deadline, monotonic_fn=monotonic_fn):
                    raise RuntimeError(f'wait timed out for {job_id}')
                try:
                    handle = connect_mounted_daemon_fn(context, allow_restart_stale=True)
                except reconnect_error_classes:
                    sleep_fn(poll_interval)
                    continue
                assert handle.client is not None
                client = handle.client
            sleep_fn(poll_interval)
            continue

        batch = _watch_batch_from_payload(job_id, payload)
        if emit_output and batch.events:
            write_lines_fn(out, render_watch_batch_fn(batch))
        cursor = batch.cursor
        if batch.terminal:
            if emit_output and not batch.events:
                write_lines_fn(out, render_watch_batch_fn(batch))
            return batch
        if _deadline_exceeded(deadline, monotonic_fn=monotonic_fn):
            raise RuntimeError(f'wait timed out for {job_id}')
        sleep_fn(poll_interval)


def _watch_deadline(
    timeout: float | None,
    *,
    timeout_seconds_fn: Callable[[], float],
    monotonic_fn: Callable[[], float],
) -> float | None:
    timeout_s = timeout_seconds_fn() if timeout is None else float(timeout)
    if timeout_s <= 0:
        return None
    return monotonic_fn() + timeout_s


def _deadline_exceeded(deadline: float | None, *, monotonic_fn: Callable[[], float]) -> bool:
    return deadline is not None and monotonic_fn() > deadline


def _watch_batch_from_payload(job_id: str, payload: dict) -> WatchEventBatch:
    return WatchEventBatch(
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
        events=tuple(payload.get('events', ())),
    )


__all__ = ['watch_ask_job']
