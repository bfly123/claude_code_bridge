from __future__ import annotations

from pathlib import Path
import threading

from .lifecycle import listen_server, shutdown_server
from .loop import serve_forever as serve_forever_impl
from .protocol import handle_connection


class CcbdSocketServer:
    _MUTATING_OPS = frozenset({'submit', 'cancel', 'attach', 'start', 'restore', 'ack', 'stop-all'})
    _DOUBLE_TICK_OPS = frozenset({'submit'})

    def __init__(self, socket_path: str | Path) -> None:
        self._socket_path = Path(socket_path)
        self._handlers: dict[str, callable] = {}
        self._server = None
        self._stop_event = threading.Event()

    @property
    def socket_path(self) -> Path:
        return self._socket_path

    def register_handler(self, op: str, handler) -> None:
        if op in self._handlers:
            raise ValueError(f'duplicate handler for op {op!r}')
        self._handlers[op] = handler

    def listen(self) -> None:
        listen_server(self)

    def serve_forever(self, *, poll_interval: float = 0.2, on_tick=None) -> None:
        serve_forever_impl(self, poll_interval=poll_interval, on_tick=on_tick)

    def shutdown(self) -> None:
        shutdown_server(self)

    def _handle_connection(self, conn) -> str | None:
        return handle_connection(self, conn)


__all__ = ['CcbdSocketServer']
