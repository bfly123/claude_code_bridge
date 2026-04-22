from __future__ import annotations

from ccbd.ipc import build_server_transport


def listen_server(server) -> None:
    if server._transport is not None:
        return
    server._transport = build_server_transport(server._socket_path, ipc_kind=server._ipc_kind)
    server._transport.listen()
    server._server = server._transport
    server._stop_event.clear()


def shutdown_server(server) -> None:
    server._stop_event.set()
    if server._transport is not None:
        try:
            server._transport.close()
        finally:
            server._transport = None
    server._server = None


__all__ = ['listen_server', 'shutdown_server']
