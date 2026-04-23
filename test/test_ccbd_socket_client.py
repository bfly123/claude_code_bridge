from __future__ import annotations

import pytest

from ccbd.socket_client import CcbdClient, CcbdClientError


def test_ccbd_client_uses_stable_default_timeout(tmp_path) -> None:
    client = CcbdClient(tmp_path / "ccbd.sock")
    assert client._timeout_s == 30.0


def test_ccbd_client_reads_timeout_from_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CCB_CCBD_CLIENT_TIMEOUT_S", "4.5")
    client = CcbdClient(tmp_path / "ccbd.sock")
    assert client._timeout_s == 4.5


def test_ccbd_client_explicit_timeout_overrides_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CCB_CCBD_CLIENT_TIMEOUT_S", "4.5")
    client = CcbdClient(tmp_path / "ccbd.sock", timeout_s=0.2)
    assert client._timeout_s == 0.2


def test_ccbd_client_dynamic_submit_endpoint_uses_request(monkeypatch, tmp_path) -> None:
    client = CcbdClient(tmp_path / "ccbd.sock")
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(client, 'request', lambda op, payload=None: calls.append((op, payload)) or {'ok': True})

    class Envelope:
        def to_record(self) -> dict:
            return {'to_agent': 'agent1', 'body': 'hello'}

    envelope = Envelope()
    payload = client.submit(envelope)

    assert payload == {'ok': True}
    assert calls and calls[0][0] == 'submit'
    assert calls[0][1]['to_agent'] == 'agent1'


def test_ccbd_client_dynamic_attach_endpoint_builds_payload(monkeypatch, tmp_path) -> None:
    client = CcbdClient(tmp_path / "ccbd.sock")
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(client, 'request', lambda op, payload=None: calls.append((op, payload)) or {'ok': True})

    payload = client.attach(
        agent_name='agent3',
        workspace_path='/tmp/work',
        backend_type='pane-backed',
        pane_id='%9',
        binding_source='external-attach',
    )

    assert payload == {'ok': True}
    assert calls == [
        (
            'attach',
            {
                'agent_name': 'agent3',
                'workspace_path': '/tmp/work',
                'backend_type': 'pane-backed',
                'pid': None,
                'runtime_ref': None,
                'session_ref': None,
                'health': None,
                'provider': None,
                'runtime_root': None,
                'runtime_pid': None,
                'terminal_backend': None,
                'pane_id': '%9',
                'active_pane_id': None,
                'pane_title_marker': None,
                'pane_state': None,
                'tmux_socket_name': None,
                'session_file': None,
                'session_id': None,
                'lifecycle_state': None,
                'managed_by': None,
                'binding_source': 'external-attach',
            },
        )
    ]


def test_ccbd_client_dynamic_shutdown_endpoint_uses_empty_payload(monkeypatch, tmp_path) -> None:
    client = CcbdClient(tmp_path / "ccbd.sock")
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(client, 'request', lambda op, payload=None: calls.append((op, payload)) or {'ok': True})

    client.shutdown()

    assert calls == [('shutdown', {})]


def test_ccbd_client_request_wraps_socket_connect_errors(monkeypatch, tmp_path) -> None:
    client = CcbdClient(tmp_path / "ccbd.sock")

    monkeypatch.setattr(
        'ccbd.socket_client.connect_socket',
        lambda socket_path, *, timeout_s: (_ for _ in ()).throw(ConnectionRefusedError('[Errno 111] Connection refused')),
    )

    with pytest.raises(CcbdClientError, match='Connection refused'):
        client.request('ping', {})
