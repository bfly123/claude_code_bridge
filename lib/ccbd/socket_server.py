from __future__ import annotations

from pathlib import Path
import json
import socket
import threading
import time

from ccbd.api_models import RpcRequest, RpcResponse


class CcbdSocketServer:
    _MUTATING_OPS = frozenset({'submit', 'cancel', 'attach', 'start', 'restore', 'ack', 'stop-all'})
    _DOUBLE_TICK_OPS = frozenset({'submit'})

    def __init__(self, socket_path: str | Path) -> None:
        self._socket_path = Path(socket_path)
        self._handlers: dict[str, callable] = {}
        self._server: socket.socket | None = None
        self._stop_event = threading.Event()

    @property
    def socket_path(self) -> Path:
        return self._socket_path

    def register_handler(self, op: str, handler) -> None:
        if op in self._handlers:
            raise ValueError(f'duplicate handler for op {op!r}')
        self._handlers[op] = handler

    def listen(self) -> None:
        if self._server is not None:
            return
        if not hasattr(socket, 'AF_UNIX'):
            raise RuntimeError('unix domain sockets are not supported on this platform')
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self._socket_path.exists():
            self._socket_path.unlink()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self._socket_path))
        server.listen(16)
        server.settimeout(0.2)
        self._server = server
        self._stop_event.clear()

    def serve_forever(self, *, poll_interval: float = 0.2, on_tick=None) -> None:
        self.listen()
        interval = max(0.0, float(poll_interval))
        next_tick_at = time.monotonic() + interval
        while not self._stop_event.is_set():
            server = self._server
            if server is None:
                break
            timeout = None
            if on_tick is not None:
                timeout = max(0.0, next_tick_at - time.monotonic())
            server.settimeout(timeout)
            try:
                conn, _ = server.accept()
            except socket.timeout:
                if on_tick is not None:
                    on_tick()
                    next_tick_at = time.monotonic() + interval
                continue
            except OSError:
                break
            with conn:
                handled_op = self._handle_connection(conn)
            if self._stop_event.is_set():
                continue
            if on_tick is not None and handled_op in self._MUTATING_OPS:
                on_tick()
                if handled_op in self._DOUBLE_TICK_OPS:
                    on_tick()
                next_tick_at = time.monotonic() + interval
                continue
            if on_tick is not None and time.monotonic() >= next_tick_at:
                on_tick()
                next_tick_at = time.monotonic() + interval

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._server is not None:
            try:
                self._server.close()
            finally:
                self._server = None
        try:
            if self._socket_path.exists():
                self._socket_path.unlink()
        except FileNotFoundError:
            pass

    def _handle_connection(self, conn: socket.socket) -> str | None:
        raw = b''
        while b'\n' not in raw:
            chunk = conn.recv(65536)
            if not chunk:
                break
            raw += chunk
        if not raw:
            return None
        request = None
        try:
            message = json.loads(raw.split(b'\n', 1)[0].decode('utf-8'))
            request = RpcRequest.from_record(message)
            handler = self._handlers.get(request.op)
            if handler is None:
                response = RpcResponse.failure(f'unknown op: {request.op}')
            else:
                response = RpcResponse.success(handler(request.request))
        except Exception as exc:
            response = RpcResponse.failure(str(exc))
        try:
            conn.sendall((json.dumps(response.to_record(), ensure_ascii=False) + '\n').encode('utf-8'))
        except OSError:
            # Clients may disconnect immediately after writing the request.
            # Treat response delivery as best-effort so a broken pipe cannot
            # take down the daemon event loop.
            return getattr(request, 'op', None)
        return getattr(request, 'op', None)


__all__ = ['CcbdSocketServer']
