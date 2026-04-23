from __future__ import annotations

import os
import socket
import time


def listen_server(server) -> None:
    if server._server is not None:
        return
    if not hasattr(socket, 'AF_UNIX'):
        raise RuntimeError('unix domain sockets are not supported on this platform')
    server._socket_path.parent.mkdir(parents=True, exist_ok=True)
    if server._socket_path.exists():
        server._socket_path.unlink()
    runtime_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    runtime_socket.bind(str(server._socket_path))
    runtime_socket.listen(16)
    runtime_socket.settimeout(0.2)
    server._server = runtime_socket
    server._bound_socket_stat = _bound_socket_stat(server._socket_path)
    server._stop_event.clear()


def shutdown_server(server) -> None:
    server._stop_event.set()
    bound_socket_stat = server._bound_socket_stat
    if server._server is not None:
        try:
            server._server.close()
        finally:
            server._server = None
    _unlink_bound_socket_path(server, bound_socket_stat=bound_socket_stat)
    server._bound_socket_stat = None


def _bound_socket_stat(path) -> tuple[int, int] | None:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return int(stat.st_dev), int(stat.st_ino)


def _unlink_bound_socket_path(
    server,
    *,
    bound_socket_stat: tuple[int, int] | None,
    timeout_s: float = 0.2,
) -> None:
    if bound_socket_stat is None:
        return
    deadline = time.monotonic() + max(0.0, float(timeout_s))
    while True:
        try:
            current = _bound_socket_stat(server._socket_path)
            if current is None or current != bound_socket_stat:
                return
            server._socket_path.unlink()
            return
        except FileNotFoundError:
            return
        except OSError:
            if time.monotonic() >= deadline:
                return
            time.sleep(0.01)


__all__ = ['listen_server', 'shutdown_server']
