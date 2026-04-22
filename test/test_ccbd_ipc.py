from __future__ import annotations

from pathlib import Path

import ccbd.ipc as ipc
import pytest
import threading
import time


def test_normalize_ipc_kind_detects_named_pipe_ref() -> None:
    assert ipc.normalize_ipc_kind(None, r'\\.\pipe\ccb-test') == 'named_pipe'


def test_endpoint_connectable_short_circuits_missing_unix_marker(monkeypatch, tmp_path: Path) -> None:
    marker = tmp_path / 'missing.sock'
    called: list[str] = []

    monkeypatch.setattr(ipc, '_supports_unix_sockets', lambda: False)
    monkeypatch.setattr(
        ipc,
        'connect_client',
        lambda endpoint_ref, *, timeout_s, ipc_kind=None: called.append(str(endpoint_ref)),
    )

    assert ipc.endpoint_connectable(marker, ipc_kind='unix_socket') is False
    assert called == []


def test_endpoint_connectable_handles_pipe_connect_timeout(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / 'missing.sock'
    path.write_text('', encoding='utf-8')
    called = []

    def _timeout(*args, **kwargs):
        called.append('timeout')
        raise TimeoutError('timeout')

    monkeypatch.setattr(ipc, '_supports_unix_sockets', lambda: False)
    monkeypatch.setattr(ipc, '_wait_for_pipe', lambda *args, **kwargs: None)
    monkeypatch.setattr(ipc, '_connect_pipe', _timeout)
    assert ipc.endpoint_connectable(path, timeout_s=0.1, ipc_kind='unix_socket') is False
    assert called == ['timeout']


def test_wait_for_pipe_forwards_timeout(monkeypatch) -> None:
    seen: list[float] = []

    def _fake_wait_for_pipe_once(endpoint_ref: str, *, timeout_s: float) -> None:
        seen.append(timeout_s)
        raise TimeoutError('fake')

    monkeypatch.setattr(ipc, '_wait_for_pipe_once', _fake_wait_for_pipe_once)
    with pytest.raises(TimeoutError, match='fake'):
        ipc._wait_for_pipe('\\\\.\\pipe\\test', timeout_s=0.37)
    assert seen == [0.37]


def test_connect_client_uses_compat_pipe_for_unix_socket_on_windows(monkeypatch, tmp_path: Path) -> None:
    socket_path = tmp_path / 'ccbd.sock'
    socket_path.write_text('', encoding='utf-8')
    called: list[str] = []

    monkeypatch.setattr(ipc, '_supports_unix_sockets', lambda: False)
    monkeypatch.setattr(
        ipc,
        '_connect_pipe_client',
        lambda endpoint_ref, *, timeout_s: called.append(str(endpoint_ref)) or object(),
    )

    assert ipc.connect_client(socket_path, timeout_s=0.2, ipc_kind='unix_socket') is not None
    assert called == [str(ipc._compat_pipe_ref(socket_path))]


def test_pipe_connection_adapter_raises_timeout_instead_of_eof() -> None:
    class _Conn:
        def poll(self, timeout):
            return False

    adapter = ipc._PipeConnectionAdapter(_Conn(), timeout_s=0.25)

    with pytest.raises(TimeoutError, match='named pipe data'):
        adapter.recv(1024)


def test_pipe_connection_adapter_times_out_when_poll_blocks() -> None:
    class _Conn:
        def poll(self, timeout):
            time.sleep(1)
            return True

    adapter = ipc._PipeConnectionAdapter(_Conn(), timeout_s=0.1)

    start = time.perf_counter()
    with pytest.raises(TimeoutError, match='named pipe data'):
        adapter.recv(8)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.5


def test_pipe_connection_adapter_sendall_times_out_when_write_blocks() -> None:
    class _Conn:
        def send_bytes(self, data):
            del data
            time.sleep(1)

        def close(self):
            return None

    adapter = ipc._PipeConnectionAdapter(_Conn(), timeout_s=0.1)

    start = time.perf_counter()
    with pytest.raises(TimeoutError, match='writing named pipe data'):
        adapter.sendall(b'hello')
    elapsed = time.perf_counter() - start
    assert elapsed < 0.5


def test_pipe_connection_adapter_recv_times_out_when_read_blocks_after_poll() -> None:
    class _Conn:
        def poll(self, timeout):
            del timeout
            return True

        def recv_bytes(self):
            time.sleep(1)
            return b'data'

        def close(self):
            return None

    adapter = ipc._PipeConnectionAdapter(_Conn(), timeout_s=0.1)

    start = time.perf_counter()
    with pytest.raises(TimeoutError, match='reading named pipe data'):
        adapter.recv(4)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.5


def test_start_worker_tolerates_keyboard_interrupt_after_thread_start() -> None:
    class _Thread:
        def __init__(self) -> None:
            self.calls = 0
            self._alive = False

        def start(self) -> None:
            self.calls += 1
            self._alive = True
            raise KeyboardInterrupt

        def is_alive(self) -> bool:
            return self._alive

    thread = _Thread()

    ipc._start_worker(thread, deadline=time.monotonic() + 0.1, timeout_message='timed out')

    assert thread.calls == 1


def test_start_worker_tolerates_keyboard_interrupt_during_backoff_sleep(monkeypatch) -> None:
    class _Thread:
        def __init__(self) -> None:
            self.calls = 0

        def start(self) -> None:
            self.calls += 1
            if self.calls == 1:
                raise KeyboardInterrupt

        def is_alive(self) -> bool:
            return False

    sleep_calls = {'count': 0}

    def _sleep(seconds: float) -> None:
        sleep_calls['count'] += 1
        if sleep_calls['count'] == 1:
            raise KeyboardInterrupt

    monkeypatch.setattr(ipc.time, 'sleep', _sleep)

    thread = _Thread()

    ipc._start_worker(thread, deadline=time.monotonic() + 0.1, timeout_message='timed out')

    assert thread.calls == 2
    assert sleep_calls['count'] == 1


def test_wait_for_worker_tolerates_keyboard_interrupt_before_done() -> None:
    class _Done:
        def __init__(self) -> None:
            self.calls = 0

        def wait(self, timeout) -> bool:
            del timeout
            self.calls += 1
            if self.calls == 1:
                raise KeyboardInterrupt
            return True

        def is_set(self) -> bool:
            return self.calls >= 2

    done = _Done()

    assert ipc._wait_for_worker(done, deadline=time.monotonic() + 0.1) is True
    assert done.calls == 2


def test_pipe_connection_adapter_consumes_buffer_across_reads() -> None:
    class _Conn:
        def __init__(self) -> None:
            self.calls = 0

        def poll(self, timeout):
            return True

        def recv_bytes(self):
            self.calls += 1
            return b'abcdef'

    conn = _Conn()
    adapter = ipc._PipeConnectionAdapter(conn, timeout_s=0.25)

    assert adapter.recv(2) == b'ab'
    assert adapter.recv(2) == b'cd'
    assert adapter.recv(8) == b'ef'
    assert conn.calls == 1


def test_named_pipe_server_transport_creates_listener_on_accept_thread(monkeypatch) -> None:
    state = {'creator_tid': None, 'closed': False}
    main_tid = threading.get_ident()

    class _Conn:
        def close(self) -> None:
            return None

    class _Listener:
        def __init__(self, *, address, family) -> None:
            del address, family
            state['creator_tid'] = threading.get_ident()
            self.calls = 0

        def accept(self):
            if threading.get_ident() != state['creator_tid']:
                raise PermissionError(5, 'Access is denied.')
            if self.calls == 0:
                self.calls += 1
                return _Conn()
            while not state['closed']:
                time.sleep(0.01)
            raise OSError('closed')

        def close(self) -> None:
            state['closed'] = True

    monkeypatch.setattr(ipc, '_build_named_pipe_listener', lambda endpoint_ref: _Listener(address=endpoint_ref, family='AF_PIPE'))
    monkeypatch.setattr(ipc, 'PipeClient', lambda **kwargs: _Conn())

    transport = ipc._NamedPipeServerTransport(r'\\.\pipe\ccb-threaded-listener')
    transport.listen()
    conn = transport.accept(0.2)

    assert isinstance(conn, ipc._PipeConnectionAdapter)
    assert state['creator_tid'] != main_tid
    transport.close()


def test_named_pipe_server_transport_listen_surfaces_thread_start_failure(monkeypatch) -> None:
    monkeypatch.setattr(ipc, '_build_named_pipe_listener', lambda endpoint_ref: (_ for _ in ()).throw(PermissionError(5, 'Access is denied.')))

    transport = ipc._NamedPipeServerTransport(r'\\.\pipe\ccb-listen-fail')

    with pytest.raises(OSError, match='Access is denied'):
        transport.listen()
