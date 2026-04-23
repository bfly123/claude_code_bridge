from __future__ import annotations

from dataclasses import dataclass

from .watch_fallback import load_persisted_terminal_watch_payload


_DEFAULT_POLL_INTERVAL_S = 0.1
_DEFAULT_TIMEOUT_S = 10.0


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


def default_watch_timeout_seconds() -> float:
    return _DEFAULT_TIMEOUT_S


def default_watch_poll_interval_seconds() -> float:
    return _DEFAULT_POLL_INTERVAL_S


def watch_target(
    context,
    command,
    *,
    connect_mounted_daemon_fn,
    reconnect_error_classes: tuple[type[BaseException], ...],
    time_fn,
    sleep_fn,
    timeout_seconds_fn,
    poll_interval_seconds_fn,
):
    cursor = 0
    deadline = time_fn() + timeout_seconds_fn()
    try:
        handle = connect_mounted_daemon_fn(context, allow_restart_stale=True)
    except reconnect_error_classes:
        fallback = _persisted_terminal_batch(context, command.target, cursor=cursor)
        if fallback is not None:
            yield fallback
            return
        raise
    assert handle.client is not None
    poll_interval = poll_interval_seconds_fn()

    while True:
        try:
            payload = handle.client.watch(command.target, cursor=cursor)
        except reconnect_error_classes:
            fallback = _persisted_terminal_batch(context, command.target, cursor=cursor)
            if fallback is not None:
                yield fallback
                return
            handle = _connect_handle(
                context,
                target=command.target,
                cursor=cursor,
                connect_mounted_daemon_fn=connect_mounted_daemon_fn,
                reconnect_error_classes=reconnect_error_classes,
                time_fn=time_fn,
                sleep_fn=sleep_fn,
                deadline=deadline,
                poll_interval_seconds_fn=poll_interval_seconds_fn,
            )
            if handle is None:
                fallback = _persisted_terminal_batch(context, command.target, cursor=cursor)
                if fallback is not None:
                    yield fallback
                    return
                raise RuntimeError(f"watch timed out for target {command.target}")
            sleep_fn(poll_interval)
            continue

        batch = _watch_batch_from_payload(command.target, payload)
        if batch.events:
            yield batch
        cursor = batch.cursor
        if batch.terminal:
            if not batch.events:
                yield batch
            return
        if _deadline_exceeded(deadline, time_fn=time_fn):
            fallback = _persisted_terminal_batch(context, command.target, cursor=cursor)
            if fallback is not None:
                yield fallback
                return
            raise RuntimeError(f"watch timed out for target {command.target}")
        sleep_fn(poll_interval)


def _deadline_exceeded(deadline: float, *, time_fn) -> bool:
    return time_fn() > deadline


def _watch_batch_from_payload(target: str, payload: dict) -> WatchEventBatch:
    return WatchEventBatch(
        target=target,
        job_id=payload["job_id"],
        agent_name=payload["agent_name"],
        target_kind=payload.get("target_kind"),
        target_name=payload.get("target_name") or payload.get("agent_name") or "",
        provider=payload.get("provider"),
        provider_instance=payload.get("provider_instance"),
        cursor=int(payload["cursor"]),
        generation=int(payload["generation"]) if payload.get("generation") is not None else None,
        terminal=bool(payload["terminal"]),
        status=payload.get("status"),
        reply=payload.get("reply") or "",
        events=tuple(payload.get("events", [])),
    )


def _connect_handle(
    context,
    *,
    target: str,
    cursor: int,
    connect_mounted_daemon_fn,
    reconnect_error_classes: tuple[type[BaseException], ...],
    time_fn,
    sleep_fn,
    deadline: float | None,
    poll_interval_seconds_fn,
):
    poll_interval = poll_interval_seconds_fn()
    while True:
        if deadline is not None and _deadline_exceeded(deadline, time_fn=time_fn):
            return None
        try:
            handle = connect_mounted_daemon_fn(context, allow_restart_stale=True)
        except reconnect_error_classes:
            fallback = _persisted_terminal_batch(context, target, cursor=cursor)
            if fallback is not None:
                return None
            sleep_fn(poll_interval)
            continue
        assert handle.client is not None
        return handle


def _persisted_terminal_batch(context, target: str, *, cursor: int) -> WatchEventBatch | None:
    payload = load_persisted_terminal_watch_payload(context, target, cursor=cursor)
    if payload is None:
        return None
    return _watch_batch_from_payload(target, payload)


__all__ = [
    "WatchEventBatch",
    "default_watch_poll_interval_seconds",
    "default_watch_timeout_seconds",
    "watch_target",
]
