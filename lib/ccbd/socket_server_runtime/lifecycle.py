from __future__ import annotations

import socket


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
    server._stop_event.clear()


def shutdown_server(server) -> None:
    server._stop_event.set()
    if server._server is not None:
        try:
            server._server.close()
        finally:
            server._server = None
    try:
        if server._socket_path.exists():
            server._socket_path.unlink()
    except FileNotFoundError:
        pass


__all__ = ['listen_server', 'shutdown_server']
