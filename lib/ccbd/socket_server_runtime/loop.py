from __future__ import annotations

import socket
import time


def serve_forever(server, *, poll_interval: float = 0.2, on_tick=None) -> None:
    server.listen()
    interval = max(0.0, float(poll_interval))
    next_tick_at = time.monotonic() + interval
    while not server._stop_event.is_set():
        runtime_socket = server._server
        if runtime_socket is None:
            break
        timeout = next_timeout(next_tick_at=next_tick_at, on_tick=on_tick)
        runtime_socket.settimeout(timeout)
        try:
            conn, _ = runtime_socket.accept()
        except socket.timeout:
            next_tick_at = run_tick_if_needed(on_tick=on_tick, next_tick_at=next_tick_at, interval=interval)
            continue
        except OSError:
            break
        with conn:
            handled_op = server._handle_connection(conn)
        if server._stop_event.is_set():
            continue
        next_tick_at = post_request_tick(
            handled_op=handled_op,
            on_tick=on_tick,
            next_tick_at=next_tick_at,
            interval=interval,
            mutating_ops=server._MUTATING_OPS,
            double_tick_ops=server._DOUBLE_TICK_OPS,
        )


def next_timeout(*, next_tick_at: float, on_tick) -> float | None:
    if on_tick is None:
        return None
    return max(0.0, next_tick_at - time.monotonic())


def run_tick_if_needed(*, on_tick, next_tick_at: float, interval: float) -> float:
    if on_tick is None:
        return next_tick_at
    on_tick()
    return time.monotonic() + interval


def post_request_tick(
    *,
    handled_op: str | None,
    on_tick,
    next_tick_at: float,
    interval: float,
    mutating_ops,
    double_tick_ops,
) -> float:
    if on_tick is not None and handled_op in mutating_ops:
        on_tick()
        if handled_op in double_tick_ops:
            on_tick()
        return time.monotonic() + interval
    if on_tick is not None and time.monotonic() >= next_tick_at:
        on_tick()
        return time.monotonic() + interval
    return next_tick_at


__all__ = ['next_timeout', 'post_request_tick', 'run_tick_if_needed', 'serve_forever']
