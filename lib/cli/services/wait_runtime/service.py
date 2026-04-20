from __future__ import annotations

import time

from .models import WaitSummary
from .policy import resolve_poll_interval, resolve_quorum, resolve_timeout
from .replies import latest_replies


def wait_for_replies(
    context,
    command,
    *,
    connect_mounted_daemon_fn,
    client_error_cls,
    service_error_cls,
    monotonic_fn=time.monotonic,
    sleep_fn=time.sleep,
) -> WaitSummary:
    timeout_s = resolve_timeout(command.timeout_s)
    poll_interval_s = resolve_poll_interval()
    started_at = monotonic_fn()
    deadline = started_at + timeout_s
    handle = connect_mounted_daemon_fn(context, allow_restart_stale=True)
    assert handle.client is not None
    while True:
        try:
            payload = handle.client.trace(command.target)
        except (client_error_cls, service_error_cls):
            if monotonic_fn() >= deadline:
                raise RuntimeError(f'wait {command.mode} timed out for target {command.target}')
            handle = connect_mounted_daemon_fn(context, allow_restart_stale=True)
            assert handle.client is not None
            sleep_fn(poll_interval_s)
            continue

        expected_count, replies, terminal_count, notice_count = latest_replies(payload)
        if expected_count <= 0:
            raise RuntimeError(f'wait target has no attempt routes: {command.target}')
        quorum = resolve_quorum(command, expected_count=expected_count)
        if len(replies) >= quorum:
            waited_s = monotonic_fn() - started_at
            wait_status = 'satisfied' if terminal_count >= quorum else 'notice'
            return WaitSummary(
                wait_status=wait_status,
                project_id=context.project.project_id,
                mode=command.mode,
                target=command.target,
                resolved_kind=str(payload.get('resolved_kind') or ''),
                expected_count=expected_count,
                received_count=len(replies),
                terminal_count=terminal_count,
                notice_count=notice_count,
                waited_s=waited_s,
                replies=tuple(replies),
            )
        if monotonic_fn() >= deadline:
            raise RuntimeError(f'wait {command.mode} timed out for target {command.target}')
        sleep_fn(poll_interval_s)


__all__ = ['wait_for_replies']
