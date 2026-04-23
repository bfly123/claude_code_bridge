from __future__ import annotations

from dataclasses import dataclass
import ctypes
import hashlib
from pathlib import Path
from queue import Empty, Queue
import os
import socket
import time
import threading
try:
    import _winapi
except ImportError:  # pragma: no cover - non-Windows
    _winapi = None

from multiprocessing.connection import Client as PipeClient
from multiprocessing.connection import Listener as PipeListener
try:
    from multiprocessing.connection import PipeConnection
except ImportError:  # pragma: no cover - non-Windows
    PipeConnection = None


IPC_KIND_UNIX_SOCKET = 'unix_socket'
IPC_KIND_NAMED_PIPE = 'named_pipe'
_PIPE_PREFIX = '\\\\.\\pipe\\'


def _supports_unix_sockets() -> bool:
    return hasattr(socket, 'AF_UNIX')


def _compat_pipe_ref(endpoint_ref: str | Path) -> str:
    digest = hashlib.sha1(str(endpoint_ref).encode('utf-8', errors='ignore')).hexdigest()[:20]
    return fr'\\.\pipe\ccb-unix-compat-{digest}'


def normalize_ipc_kind(ipc_kind: str | None, endpoint_ref: str | Path | None = None) -> str:
    raw = str(ipc_kind or '').strip().lower()
    if raw in {IPC_KIND_UNIX_SOCKET, IPC_KIND_NAMED_PIPE}:
        return raw
    endpoint_text = str(endpoint_ref or '').strip()
    if endpoint_text.startswith(_PIPE_PREFIX):
        return IPC_KIND_NAMED_PIPE
    return IPC_KIND_UNIX_SOCKET


def endpoint_exists(endpoint_ref: str | Path, *, ipc_kind: str | None = None) -> bool:
    resolved_kind = normalize_ipc_kind(ipc_kind, endpoint_ref)
    if resolved_kind == IPC_KIND_NAMED_PIPE:
        return False
    return Path(endpoint_ref).exists()


def endpoint_connectable(endpoint_ref: str | Path, *, timeout_s: float = 0.2, ipc_kind: str | None = None) -> bool:
    resolved_kind = normalize_ipc_kind(ipc_kind, endpoint_ref)
    if resolved_kind != IPC_KIND_NAMED_PIPE and not _supports_unix_sockets() and not Path(endpoint_ref).exists():
        return False
    try:
        conn = connect_client(endpoint_ref, timeout_s=timeout_s, ipc_kind=ipc_kind)
    except (OSError, TimeoutError):
        return False
    try:
        return True
    finally:
        conn.close()


def connect_client(endpoint_ref: str | Path, *, timeout_s: float, ipc_kind: str | None = None):
    resolved_kind = normalize_ipc_kind(ipc_kind, endpoint_ref)
    if resolved_kind == IPC_KIND_NAMED_PIPE:
        return _connect_pipe_client(str(endpoint_ref), timeout_s=timeout_s)
    if not _supports_unix_sockets():
        if not Path(endpoint_ref).exists():
            raise OSError(f'unix socket marker is missing: {endpoint_ref}')
        return _connect_pipe_client(_compat_pipe_ref(endpoint_ref), timeout_s=timeout_s)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout_s)
    try:
        sock.connect(str(endpoint_ref))
    except OSError:
        sock.close()
        raise
    return sock


def _connect_pipe_client(endpoint_ref: str, *, timeout_s: float):
    _wait_for_pipe(endpoint_ref, timeout_s=timeout_s)
    connection = _connect_pipe(endpoint_ref, timeout_s=timeout_s)
    return _PipeConnectionAdapter(connection, timeout_s=timeout_s)


def _connect_pipe(endpoint_ref: str, *, timeout_s: float):
    deadline = time.monotonic() + timeout_s
    last_error: BaseException | None = None
    while True:
        try:
            return PipeClient(address=endpoint_ref, family='AF_PIPE')
        except BaseException as exc:
            last_error = exc
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if last_error is None:
                raise TimeoutError('timed out waiting for named pipe connection')
            if isinstance(last_error, TimeoutError):
                raise last_error
            raise TimeoutError('timed out waiting for named pipe connection') from last_error
        time.sleep(min(0.05, max(0.01, remaining)))


def _wait_for_pipe(endpoint_ref: str, *, timeout_s: float) -> None:
    deadline = time.monotonic() + max(0.0, float(timeout_s))
    last_error: BaseException | None = None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if last_error is None:
                raise TimeoutError('timed out waiting for named pipe availability')
            if isinstance(last_error, TimeoutError):
                raise last_error
            raise TimeoutError('timed out waiting for named pipe availability') from last_error
        try:
            _wait_for_pipe_once(endpoint_ref, timeout_s=min(0.2, remaining))
            return
        except BaseException as exc:
            last_error = exc
        sleep_s = min(0.05, max(0.0, deadline - time.monotonic()))
        if sleep_s > 0:
            time.sleep(sleep_s)


def _wait_for_pipe_once(endpoint_ref: str, *, timeout_s: float) -> None:
    if os.name != 'nt':
        return
    kernel32 = getattr(ctypes, 'windll', None)
    if kernel32 is None:
        return
    wait_fn = getattr(kernel32.kernel32, 'WaitNamedPipeW', None)
    if wait_fn is None:
        return
    wait_ms = max(1, int(float(timeout_s) * 1000))
    if wait_fn(endpoint_ref, wait_ms):
        return
    error_code = ctypes.GetLastError()
    raise OSError(error_code, f'named pipe unavailable: {endpoint_ref}')


def build_server_transport(endpoint_ref: str | Path, *, ipc_kind: str | None = None):
    resolved_kind = normalize_ipc_kind(ipc_kind, endpoint_ref)
    if resolved_kind == IPC_KIND_NAMED_PIPE:
        return _NamedPipeServerTransport(str(endpoint_ref))
    if not _supports_unix_sockets():
        return _CompatUnixSocketServerTransport(Path(endpoint_ref))
    return _UnixSocketServerTransport(Path(endpoint_ref))


class _PipeConnectionAdapter:
    def __init__(self, connection, *, timeout_s: float | None = None) -> None:
        self._connection = connection
        self._timeout_s = timeout_s
        self._buffer = b''

    def recv(self, size: int) -> bytes:
        if not self._buffer:
            if self._timeout_s is not None and not _connection_has_data(self._connection, self._timeout_s):
                raise TimeoutError('timed out waiting for named pipe data')
            try:
                self._buffer = _run_connection_operation(
                    self._connection,
                    timeout_s=self._timeout_s,
                    operation=self._connection.recv_bytes,
                    timeout_message='timed out reading named pipe data',
                    close_on_timeout=self._timeout_s is not None,
                )
            except EOFError:
                return b''
            except OSError as exc:
                if isinstance(exc, TimeoutError):
                    raise
                return b''
        chunk = self._buffer[:size]
        self._buffer = self._buffer[size:]
        return chunk

    def sendall(self, data: bytes) -> None:
        _run_connection_operation(
            self._connection,
            timeout_s=self._timeout_s,
            operation=lambda: self._connection.send_bytes(bytes(data)),
            timeout_message='timed out writing named pipe data',
            close_on_timeout=self._timeout_s is not None,
        )

    def close(self) -> None:
        try:
            self._connection.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class _SingleInstanceNamedPipeListener:
    def __init__(self, endpoint_ref: str) -> None:
        if _winapi is None or PipeConnection is None:
            raise RuntimeError('single-instance named pipe listener is unavailable')
        self._endpoint_ref = str(endpoint_ref)
        self._first = True
        self._pending_handle = None

    def accept(self):
        handle = self._new_handle()
        try:
            overlapped = _winapi.ConnectNamedPipe(handle, overlapped=True)
        except OSError as exc:
            if exc.winerror not in {_winapi.ERROR_NO_DATA, _winapi.ERROR_PIPE_CONNECTED}:
                _winapi.CloseHandle(handle)
                raise
        else:
            try:
                _winapi.WaitForMultipleObjects([overlapped.event], False, _winapi.INFINITE)
            except BaseException:
                overlapped.cancel()
                _winapi.CloseHandle(handle)
                raise
            finally:
                _, err = overlapped.GetOverlappedResult(True)
                assert err == 0
        return PipeConnection(handle)

    def close(self) -> None:
        handle, self._pending_handle = self._pending_handle, None
        if handle is not None:
            try:
                _winapi.CloseHandle(handle)
            except Exception:
                pass

    def _new_handle(self):
        if self._pending_handle is not None:
            handle, self._pending_handle = self._pending_handle, None
            return handle
        flags = _winapi.PIPE_ACCESS_DUPLEX | _winapi.FILE_FLAG_OVERLAPPED
        if self._first:
            flags |= _winapi.FILE_FLAG_FIRST_PIPE_INSTANCE
            self._first = False
        return _winapi.CreateNamedPipe(
            self._endpoint_ref,
            flags,
            _winapi.PIPE_TYPE_MESSAGE | _winapi.PIPE_READMODE_MESSAGE | _winapi.PIPE_WAIT,
            1,
            65536,
            65536,
            _winapi.NMPWAIT_WAIT_FOREVER,
            _winapi.NULL,
        )


def _build_named_pipe_listener(endpoint_ref: str):
    if os.name == 'nt' and _winapi is not None and PipeConnection is not None:
        return _SingleInstanceNamedPipeListener(endpoint_ref)
    return PipeListener(address=endpoint_ref, family='AF_PIPE')


def _connection_has_data(connection, timeout_s: float) -> bool:
    return bool(
        _run_connection_operation(
            connection,
            timeout_s=timeout_s,
            operation=lambda: connection.poll(timeout_s),
            timeout_message='timed out waiting for named pipe data',
            close_on_timeout=True,
        )
    )


def _run_connection_operation(
    connection,
    *,
    timeout_s: float | None,
    operation,
    timeout_message: str,
    close_on_timeout: bool,
):
    done = threading.Event()
    result: dict[str, object] = {}

    def _worker() -> None:
        try:
            result['value'] = operation()
        except BaseException as exc:
            result['error'] = exc
        finally:
            done.set()

    deadline = None if timeout_s is None else time.monotonic() + timeout_s
    thread = threading.Thread(target=_worker, daemon=True)
    _start_worker(thread, deadline=deadline, timeout_message=timeout_message)
    if not _wait_for_worker(done, deadline=deadline):
        if close_on_timeout:
            try:
                connection.close()
            except Exception:
                pass
        raise TimeoutError(timeout_message)
    if 'error' in result and isinstance(result['error'], BaseException):
        raise result['error']
    return result.get('value')


def _start_worker(thread: threading.Thread, *, deadline: float | None, timeout_message: str) -> None:
    while True:
        try:
            thread.start()
            return
        except KeyboardInterrupt:
            if thread.is_alive():
                return
            if _deadline_expired(deadline):
                raise TimeoutError(timeout_message)
            try:
                time.sleep(0.01)
            except KeyboardInterrupt:
                continue


def _wait_for_worker(done: threading.Event, *, deadline: float | None) -> bool:
    while True:
        timeout = None if deadline is None else max(0.0, deadline - time.monotonic())
        if timeout == 0.0:
            return done.is_set()
        try:
            if done.wait(timeout):
                return True
        except KeyboardInterrupt:
            if _deadline_expired(deadline):
                return done.is_set()
            continue
        if deadline is None:
            continue
        return done.is_set()


def _deadline_expired(deadline: float | None) -> bool:
    return deadline is not None and time.monotonic() >= deadline


@dataclass
class _UnixSocketServerTransport:
    endpoint_ref: Path

    def __post_init__(self) -> None:
        self._server = None

    def listen(self) -> None:
        if self._server is not None:
            return
        if not hasattr(socket, 'AF_UNIX'):
            raise RuntimeError('unix domain sockets are not supported on this platform')
        self.endpoint_ref.parent.mkdir(parents=True, exist_ok=True)
        if self.endpoint_ref.exists():
            self.endpoint_ref.unlink()
        runtime_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        runtime_socket.bind(str(self.endpoint_ref))
        runtime_socket.listen(16)
        self._server = runtime_socket

    def accept(self, timeout_s: float | None):
        if self._server is None:
            return None
        self._server.settimeout(timeout_s)
        try:
            conn, _ = self._server.accept()
        except socket.timeout:
            return None
        return conn

    def close(self) -> None:
        if self._server is not None:
            try:
                self._server.close()
            finally:
                self._server = None
        try:
            if self.endpoint_ref.exists():
                self.endpoint_ref.unlink()
        except FileNotFoundError:
            pass


class _NamedPipeServerTransport:
    def __init__(self, endpoint_ref: str) -> None:
        self.endpoint_ref = str(endpoint_ref)
        self._listener = None
        self._queue: Queue[object] = Queue()
        self._accept_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._accept_error: BaseException | None = None

    def listen(self) -> None:
        if self._accept_thread is not None and self._accept_thread.is_alive():
            return
        self._stop_event.clear()
        self._ready_event.clear()
        self._accept_error = None
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()
        if not self._ready_event.wait(timeout=_named_pipe_listener_ready_timeout_s()):
            raise TimeoutError(f'timed out starting named pipe listener: {self.endpoint_ref}')
        if self._accept_error is not None:
            error = self._accept_error
            self.close()
            raise OSError(str(error))

    def accept(self, timeout_s: float | None):
        if self._accept_error is not None:
            error = self._accept_error
            if os.name == 'nt':
                self._restart_after_accept_error()
            else:
                raise OSError(str(error))
            raise OSError(str(error))
        try:
            item = self._queue.get(timeout=timeout_s)
        except Empty:
            return None
        if item is None:
            return None
        return item

    def close(self) -> None:
        self._stop_event.set()
        self._wake_listener()
        listener = self._listener
        if listener is not None:
            try:
                listener.close()
            except Exception:
                pass
        self._queue.put_nowait(None)
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=1.0)
            self._accept_thread = None
        self._listener = None

    def _accept_loop(self) -> None:
        listener = None
        while not self._stop_event.is_set():
            try:
                if listener is None:
                    listener = _build_named_pipe_listener(self.endpoint_ref)
                    self._listener = listener
                    self._ready_event.set()
                conn = listener.accept()
            except Exception as exc:
                if listener is None:
                    self._ready_event.set()
                if self._stop_event.is_set():
                    break
                self._accept_error = exc
                self._queue.put_nowait(None)
                break
            if self._stop_event.is_set():
                try:
                    conn.close()
                except Exception:
                    pass
                break
            self._queue.put_nowait(_PipeConnectionAdapter(conn))
        if listener is not None:
            try:
                listener.close()
            except Exception:
                pass
        self._listener = None
        self._ready_event.set()

    def _wake_listener(self) -> None:
        try:
            wake = PipeClient(address=self.endpoint_ref, family='AF_PIPE')
            wake.close()
        except Exception:
            pass

    def _restart_after_accept_error(self) -> None:
        listener = self._listener
        self._listener = None
        self._accept_error = None
        self._accept_thread = None
        if listener is not None:
            try:
                listener.close()
            except Exception:
                pass
        self.listen()


def _named_pipe_listener_ready_timeout_s() -> float:
    return 5.0


class _CompatUnixSocketServerTransport:
    def __init__(self, endpoint_ref: Path) -> None:
        self.endpoint_ref = Path(endpoint_ref)
        self._pipe = _NamedPipeServerTransport(_compat_pipe_ref(self.endpoint_ref))

    def listen(self) -> None:
        self.endpoint_ref.parent.mkdir(parents=True, exist_ok=True)
        self.endpoint_ref.write_text('', encoding='utf-8')
        self._pipe.listen()

    def accept(self, timeout_s: float | None):
        return self._pipe.accept(timeout_s)

    def close(self) -> None:
        self._pipe.close()
        try:
            self.endpoint_ref.unlink(missing_ok=True)
        except Exception:
            pass


__all__ = [
    'IPC_KIND_NAMED_PIPE',
    'IPC_KIND_UNIX_SOCKET',
    'build_server_transport',
    'connect_client',
    'endpoint_connectable',
    'endpoint_exists',
    'normalize_ipc_kind',
]
