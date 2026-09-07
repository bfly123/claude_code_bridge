from __future__ import annotations

import json
from pathlib import Path
import socket
import tempfile
import threading
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

import mobile_gateway.project_registry as project_registry
from ccbd.control_plane_transport.endpoint import endpoint_from_record
from ccbd.control_plane_transport.endpoint_store import write_endpoint
from cli.services.mobile import _public_gateway_url, prepare_server_mobile_gateway
from mobile_gateway import (
    MobileGatewayProject,
    MobileGatewayProjectRegistry,
    discover_running_mobile_gateway_projects,
    load_mobile_gateway_project_registry,
    publish_mobile_gateway_project,
)
from mobile_gateway.project_registry import _control_plane_endpoint_is_structurally_valid
from project.ids import compute_project_id


requires_af_unix = pytest.mark.skipif(
    not hasattr(socket, 'AF_UNIX'),
    reason='requires AF_UNIX socket support',
)


def test_registry_replaces_same_root_but_preserves_same_name(tmp_path, monkeypatch):
    registry_path = tmp_path / 'projects.json'
    first = tmp_path / 'one' / 'project'
    second = tmp_path / 'two' / 'project'
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    monkeypatch.setattr(project_registry, '_control_plane_endpoint_is_structurally_valid', lambda _: True)
    for project_id, root in [('old', first), ('other', second), ('new', first / '..' / 'project')]:
        publish_mobile_gateway_project(project_id=project_id, project_root=root,
                                       ccbd_socket_path=root / 'socket', registry_path=registry_path)
    records = json.loads(registry_path.read_text())['projects']
    assert {record['project_id'] for record in records} == {'new', 'other'}


def test_registry_rejects_stale_identity_on_load_and_publish(tmp_path, monkeypatch):
    from project.identity_store import ensure_project_identity

    root = tmp_path / 'project'
    root.mkdir()
    registry_path = tmp_path / 'projects.json'
    publish_mobile_gateway_project(project_id='old', project_root=root,
                                   ccbd_socket_path=root / 'socket', registry_path=registry_path)
    (root / '.ccb').mkdir()
    identity = ensure_project_identity(root)
    monkeypatch.setattr(project_registry, '_control_plane_endpoint_is_structurally_valid', lambda _: True)
    with pytest.raises(ValueError, match='cannot be empty'):
        load_mobile_gateway_project_registry(registry_path=registry_path)
    publish_mobile_gateway_project(project_id=identity.project_id, project_root=root,
                                   ccbd_socket_path=root / 'socket', registry_path=registry_path)
    publish_mobile_gateway_project(project_id='old', project_root=root,
                                   ccbd_socket_path=root / 'socket', registry_path=registry_path)
    assert [p.project_id for p in load_mobile_gateway_project_registry(registry_path=registry_path).projects()] == [identity.project_id]


def test_project_health_rejects_foreign_identity(tmp_path):
    from mobile_gateway.service import MobileGatewayService

    project = MobileGatewayProject(project_id='old', project_root=tmp_path,
        ccbd_client_factory=lambda: _FakeCcbdClient(project_id='current', project_root=str(tmp_path), display_name='project'))
    service = object.__new__(MobileGatewayService)
    assert service._project_list_health(project)['health'] == 'unreachable'


def _windows_tcp_loopback_endpoint(*, token_ref: str, **overrides) -> dict:
    endpoint = {
        'kind': 'tcp_loopback',
        'host': '127.0.0.1',
        'port': 32123,
        'token_ref': token_ref,
        'generation': 'test',
        'acl_status': 'windows-icacls-user-read',
        'fingerprint': 'deadbeefcafebabe',
    }
    endpoint.update(overrides)
    return endpoint


def _write_windows_tcp_marker(project_root: Path, *, endpoint: dict) -> Path:
    socket_path = project_root / '.ccb' / 'ccbd' / 'ccbd.sock'
    socket_path.parent.mkdir(parents=True)
    socket_path.touch()
    write_endpoint(endpoint_from_record(endpoint), legacy_socket_path=socket_path)
    return socket_path


def _patch_project_registry_os_name(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    os_proxy = SimpleNamespace(**vars(project_registry.os))
    os_proxy.name = name
    monkeypatch.setattr(project_registry, 'os', os_proxy)


class _FakeCcbdClient:
    def __init__(self, *, project_id: str, project_root: str, display_name: str) -> None:
        self.project_id = project_id
        self.project_root = project_root
        self.display_name = display_name
        self.calls: list[tuple[str, object]] = []

    def ping(self, target: str) -> dict[str, object]:
        self.calls.append(('ping', target))
        return {
            'status': 'ok',
            'project_id': self.project_id,
            'project_root': self.project_root,
            'display_name': self.display_name,
            'health': 'healthy',
            'mount_state': 'mounted',
        }


def test_public_gateway_url_defaults_to_loopback_fallback() -> None:
    assert (
        _public_gateway_url(None, fallback='http://127.0.0.1:8787')
        == 'http://127.0.0.1:8787'
    )
    assert (
        _public_gateway_url('', fallback='http://127.0.0.1:8787')
        == 'http://127.0.0.1:8787'
    )


def test_public_gateway_url_accepts_origin_only() -> None:
    assert (
        _public_gateway_url('https://mobile.example.com', fallback='unused')
        == 'https://mobile.example.com'
    )
    assert (
        _public_gateway_url('https://mobile.example.com/', fallback='unused')
        == 'https://mobile.example.com'
    )
    assert (
        _public_gateway_url('https://mobile.example.com:8443', fallback='unused')
        == 'https://mobile.example.com:8443'
    )


@pytest.mark.parametrize(
    ('value', 'message'),
    [
        ('mobile.example.com', 'absolute http\\(s\\) origin URL'),
        ('ftp://mobile.example.com', 'absolute http\\(s\\) origin URL'),
        ('https://mobile.example.com/pair', 'must not include a path'),
        ('https://mobile.example.com?debug=1', 'params, query, or fragment'),
        ('https://mobile.example.com#pair', 'params, query, or fragment'),
        ('https://user:pass@mobile.example.com', 'must not include credentials'),
        ('https://mobile.example.com:bad', 'port must be valid'),
    ],
)
def test_public_gateway_url_rejects_non_origin_url(value: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _public_gateway_url(value, fallback='unused')


@requires_af_unix
def test_host_project_registry_publish_and_loads_redacted_projects(tmp_path: Path) -> None:
    registry_path = tmp_path / 'mobile' / 'projects.json'
    project_root = tmp_path / 'one'
    project_root.mkdir()
    with tempfile.TemporaryDirectory(prefix='ccb-sock-', dir='/tmp') as socket_dir:
        socket_path = Path(socket_dir) / 'ccbd.sock'
        unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        unix_socket.bind(str(socket_path))
        try:
            publish_mobile_gateway_project(
                project_id='proj-one',
                project_root=project_root,
                ccbd_socket_path=socket_path,
                display_name='one',
                registry_path=registry_path,
                updated_at='2026-06-24T00:00:00Z',
            )

            payload = json.loads(registry_path.read_text(encoding='utf-8'))
            assert payload['record_type'] == 'ccb_mobile_host_project_registry'
            assert payload['projects'][0]['project_id'] == 'proj-one'
            assert payload['projects'][0]['ccbd_socket_path'] == str(socket_path)

            registry = load_mobile_gateway_project_registry(registry_path=registry_path)
            projects = registry.projects()
            assert len(projects) == 1
            assert projects[0].project_id == 'proj-one'
            assert projects[0].project_root == project_root
            assert projects[0].public_display_name == 'one'
        finally:
            unix_socket.close()
            socket_path.unlink(missing_ok=True)


def test_host_project_registry_omits_stale_persisted_projects(tmp_path: Path) -> None:
    registry_path = tmp_path / 'mobile' / 'projects.json'
    publish_mobile_gateway_project(
        project_id='proj-stale',
        project_root=tmp_path / 'missing',
        ccbd_socket_path=tmp_path / 'missing.sock',
        display_name='stale',
        registry_path=registry_path,
    )

    with pytest.raises(ValueError, match='cannot be empty'):
        load_mobile_gateway_project_registry(registry_path=registry_path)


def test_host_project_registry_loads_windows_tcp_marker_without_connecting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_project_registry_os_name(monkeypatch, 'nt')
    registry_path = tmp_path / 'mobile' / 'projects.json'
    project_root = tmp_path / 'windows-project'
    project_root.mkdir()
    socket_path = project_root / '.ccb' / 'ccbd' / 'ccbd.sock'
    socket_path.parent.mkdir(parents=True)
    socket_path.touch()
    write_endpoint(
        endpoint_from_record(
            {
                'kind': 'tcp_loopback',
                'host': '127.0.0.1',
                'port': 32123,
                'token_ref': str(socket_path.parent / 'control-plane-token-test.json'),
                'generation': 'test',
                'acl_status': 'windows-icacls-user-read',
                'fingerprint': 'deadbeefcafebabe',
            }
        ),
        legacy_socket_path=socket_path,
    )
    publish_mobile_gateway_project(
        project_id='proj-windows',
        project_root=project_root,
        ccbd_socket_path=socket_path,
        display_name='windows-project',
        registry_path=registry_path,
    )

    registry = load_mobile_gateway_project_registry(registry_path=registry_path)

    assert [project.project_id for project in registry.projects()] == ['proj-windows']
    assert registry.default_project.public_display_name == 'windows-project'


def test_host_project_registry_omits_windows_marker_with_invalid_endpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_project_registry_os_name(monkeypatch, 'nt')
    registry_path = tmp_path / 'mobile' / 'projects.json'
    project_root = tmp_path / 'windows-project'
    project_root.mkdir()
    socket_path = project_root / '.ccb' / 'ccbd' / 'ccbd.sock'
    socket_path.parent.mkdir(parents=True)
    socket_path.touch()
    (socket_path.parent / 'control-plane-endpoint.json').write_text(
        '{"kind":"tcp_loopback","host":"0.0.0.0"}',
        encoding='utf-8',
    )
    publish_mobile_gateway_project(
        project_id='proj-windows-invalid',
        project_root=project_root,
        ccbd_socket_path=socket_path,
        registry_path=registry_path,
    )

    with pytest.raises(ValueError, match='cannot be empty'):
        load_mobile_gateway_project_registry(registry_path=registry_path)


def test_windows_tcp_marker_without_endpoint_descriptor_is_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_project_registry_os_name(monkeypatch, 'nt')
    socket_path = tmp_path / '.ccb' / 'ccbd' / 'ccbd.sock'
    socket_path.parent.mkdir(parents=True)
    socket_path.touch()

    assert _control_plane_endpoint_is_structurally_valid(socket_path) is False


def test_windows_tcp_marker_with_unix_kind_descriptor_is_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_project_registry_os_name(monkeypatch, 'nt')
    socket_path = tmp_path / '.ccb' / 'ccbd' / 'ccbd.sock'
    socket_path.parent.mkdir(parents=True)
    socket_path.touch()
    (socket_path.parent / 'control-plane-endpoint.json').write_text(
        json.dumps({'kind': 'unix_socket', 'address': str(socket_path)}),
        encoding='utf-8',
    )

    assert _control_plane_endpoint_is_structurally_valid(socket_path) is False


def test_windows_tcp_marker_missing_token_ref_is_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_project_registry_os_name(monkeypatch, 'nt')
    socket_path = _write_windows_tcp_marker(
        tmp_path,
        endpoint=_windows_tcp_loopback_endpoint(token_ref=''),
    )

    assert _control_plane_endpoint_is_structurally_valid(socket_path) is False


def test_windows_tcp_marker_with_off_loopback_host_is_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_project_registry_os_name(monkeypatch, 'nt')
    socket_path = _write_windows_tcp_marker(
        tmp_path,
        endpoint=_windows_tcp_loopback_endpoint(token_ref='token', host='192.168.2.11'),
    )

    assert _control_plane_endpoint_is_structurally_valid(socket_path) is False


def test_windows_tcp_marker_with_valid_descriptor_is_valid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_project_registry_os_name(monkeypatch, 'nt')
    socket_path = _write_windows_tcp_marker(
        tmp_path,
        endpoint=_windows_tcp_loopback_endpoint(token_ref=str(tmp_path / 'token.json')),
    )

    assert _control_plane_endpoint_is_structurally_valid(socket_path) is True


def test_posix_hosts_reject_windows_tcp_marker_even_with_valid_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Linux, macOS, and WSL all report os.name == 'posix'.
    _patch_project_registry_os_name(monkeypatch, 'posix')
    socket_path = _write_windows_tcp_marker(
        tmp_path,
        endpoint=_windows_tcp_loopback_endpoint(token_ref=str(tmp_path / 'token.json')),
    )

    assert _control_plane_endpoint_is_structurally_valid(socket_path) is False


@requires_af_unix
def test_real_unix_socket_is_valid_without_endpoint_descriptor(tmp_path: Path) -> None:
    socket_path = tmp_path / 'ccbd.sock'
    unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    unix_socket.bind(str(socket_path))
    try:
        assert _control_plane_endpoint_is_structurally_valid(socket_path) is True
    finally:
        unix_socket.close()
        socket_path.unlink(missing_ok=True)


@requires_af_unix
def test_native_windows_rejects_unix_socket_representation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_project_registry_os_name(monkeypatch, 'nt')
    socket_path = tmp_path / 'ccbd.sock'
    unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    unix_socket.bind(str(socket_path))
    try:
        assert _control_plane_endpoint_is_structurally_valid(socket_path) is False
    finally:
        unix_socket.close()
        socket_path.unlink(missing_ok=True)


def test_host_project_registry_omits_windows_marker_without_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_project_registry_os_name(monkeypatch, 'nt')
    registry_path = tmp_path / 'mobile' / 'projects.json'
    project_root = tmp_path / 'windows-project'
    project_root.mkdir()
    socket_path = project_root / '.ccb' / 'ccbd' / 'ccbd.sock'
    socket_path.parent.mkdir(parents=True)
    socket_path.touch()
    publish_mobile_gateway_project(
        project_id='proj-windows-noendpoint',
        project_root=project_root,
        ccbd_socket_path=socket_path,
        registry_path=registry_path,
    )

    with pytest.raises(ValueError, match='cannot be empty'):
        load_mobile_gateway_project_registry(registry_path=registry_path)


def test_host_project_registry_omits_windows_marker_without_token_ref(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_project_registry_os_name(monkeypatch, 'nt')
    registry_path = tmp_path / 'mobile' / 'projects.json'
    project_root = tmp_path / 'windows-project'
    project_root.mkdir()
    socket_path = _write_windows_tcp_marker(
        project_root,
        endpoint=_windows_tcp_loopback_endpoint(token_ref=''),
    )
    publish_mobile_gateway_project(
        project_id='proj-windows-notoken',
        project_root=project_root,
        ccbd_socket_path=socket_path,
        registry_path=registry_path,
    )

    with pytest.raises(ValueError, match='cannot be empty'):
        load_mobile_gateway_project_registry(registry_path=registry_path)


def test_host_project_registry_omits_windows_marker_with_off_loopback_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_project_registry_os_name(monkeypatch, 'nt')
    registry_path = tmp_path / 'mobile' / 'projects.json'
    project_root = tmp_path / 'windows-project'
    project_root.mkdir()
    socket_path = _write_windows_tcp_marker(
        project_root,
        endpoint=_windows_tcp_loopback_endpoint(token_ref='token', host='192.168.2.11'),
    )
    publish_mobile_gateway_project(
        project_id='proj-windows-offloop',
        project_root=project_root,
        ccbd_socket_path=socket_path,
        registry_path=registry_path,
    )

    with pytest.raises(ValueError, match='cannot be empty'):
        load_mobile_gateway_project_registry(registry_path=registry_path)


@requires_af_unix
def test_running_project_discovery_reads_ccbd_main_project_cmdline(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'running-project'
    project_root.mkdir()
    with tempfile.TemporaryDirectory(prefix='ccb-sock-', dir='/tmp') as socket_dir:
        socket_path = Path(socket_dir) / 'ccbd.sock'
        unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        unix_socket.bind(str(socket_path))
        monkeypatch.setattr(
            'mobile_gateway.project_registry._ccbd_socket_path_for_project',
            lambda root: socket_path,
        )
        try:
            projects = discover_running_mobile_gateway_projects(
                cmdlines=[
                    ['python', '/opt/ccb/lib/ccbd/main.py', '--project', str(project_root)],
                    ['python', '/opt/ccb/lib/ccbd/keeper_main.py', '--project', str(tmp_path / 'ignored')],
                ]
            )
        finally:
            unix_socket.close()
            socket_path.unlink(missing_ok=True)

    assert len(projects) == 1
    assert projects[0].project_id == compute_project_id(project_root)
    assert projects[0].project_root == project_root.resolve()
    assert projects[0].public_display_name == 'running-project'


@requires_af_unix
def test_host_project_registry_can_merge_running_projects(tmp_path: Path, monkeypatch) -> None:
    registry_path = tmp_path / 'mobile' / 'projects.json'
    persisted_root = tmp_path / 'persisted'
    persisted_root.mkdir()
    with tempfile.TemporaryDirectory(prefix='ccb-sock-', dir='/tmp') as socket_dir:
        persisted_socket_path = Path(socket_dir) / 'persisted.sock'
        unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        unix_socket.bind(str(persisted_socket_path))
        publish_mobile_gateway_project(
            project_id='proj-persisted',
            project_root=persisted_root,
            ccbd_socket_path=persisted_socket_path,
            display_name='persisted',
            registry_path=registry_path,
        )
        running = MobileGatewayProject(
            project_id='proj-running',
            project_root=tmp_path / 'running',
            display_name='running',
            ccbd_client_factory=lambda: None,
        )
        monkeypatch.setattr(
            'mobile_gateway.project_registry.discover_running_mobile_gateway_projects',
            lambda: (running,),
        )

        try:
            registry = load_mobile_gateway_project_registry(
                registry_path=registry_path,
                include_running=True,
            )

            assert [project.project_id for project in registry.projects()] == [
                'proj-persisted',
                'proj-running',
            ]
        finally:
            unix_socket.close()
            persisted_socket_path.unlink(missing_ok=True)


def test_prepare_server_mobile_gateway_uses_running_projects(tmp_path: Path, monkeypatch) -> None:
    fake = _FakeCcbdClient(
        project_id='proj-running',
        project_root='/srv/running',
        display_name='running',
    )
    running = MobileGatewayProject(
        project_id='proj-running',
        project_root=Path('/srv/running'),
        ccbd_client_factory=lambda: fake,
        display_name='running',
    )
    monkeypatch.setattr(
        'cli.services.mobile.discover_running_mobile_gateway_projects',
        lambda: (running,),
    )
    monkeypatch.setattr('cli.services.mobile.mobile_host_state_dir', lambda: tmp_path / 'mobile-state')

    handle = prepare_server_mobile_gateway(
        SimpleNamespace(listen='127.0.0.1:0', public_url=None, route_provider='lan'),
        host_id='host-test',
    )
    try:
        assert handle.summary['project_count'] == 1
        assert handle.summary['projects'][0]['display_name'] == 'running'
        assert handle.summary['pairing']['expires_at'] is None
        assert handle.summary['pairing']['reusable_claims'] is True
    finally:
        handle.close()


def test_prepare_server_mobile_gateway_rejects_lan_listener_for_tailnet(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr('cli.services.mobile.mobile_host_state_dir', lambda: tmp_path / 'mobile-state')
    client = _FakeCcbdClient(project_id='proj-one', project_root='/srv/one', display_name='one')
    registry = MobileGatewayProjectRegistry([
        MobileGatewayProject('proj-one', Path('/srv/one'), lambda: client, display_name='one'),
    ])

    with pytest.raises(ValueError, match='loopback'):
        prepare_server_mobile_gateway(
            SimpleNamespace(
                listen='192.168.31.155:8787',
                public_url=None,
                route_provider='tailnet',
            ),
            project_registry=registry,
            host_id='host-test',
        )


def test_prepare_server_mobile_gateway_reports_redacted_push_sender_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_dir = tmp_path / 'mobile-state'
    monkeypatch.setattr('cli.services.mobile.mobile_host_state_dir', lambda: state_dir)
    monkeypatch.setattr(
        'cli.services.mobile.build_fcm_sender_from_env',
        lambda: (
            None,
            {
                'configured': True,
                'provider': 'fcm_http_v1',
                'ready': False,
                'credential_source': 'service_account_file',
                'reason': 'credential_file_unreadable',
            },
        ),
    )
    monkeypatch.setattr(
        'cli.services.mobile.fcm_sender_runtime_options',
        lambda: {'timeout_seconds': 1.25, 'max_workers': 2},
    )
    client = _FakeCcbdClient(project_id='proj-one', project_root='/srv/one', display_name='one')
    registry = MobileGatewayProjectRegistry([
        MobileGatewayProject('proj-one', Path('/srv/one'), lambda: client, display_name='one'),
    ])

    handle = prepare_server_mobile_gateway(
        SimpleNamespace(listen='127.0.0.1:0', public_url=None, route_provider='lan'),
        project_registry=registry,
        host_id='host-test',
    )
    try:
        summary = handle.summary
    finally:
        handle.close()

    assert summary['push_sender'] == {
        'configured': True,
        'provider': 'fcm_http_v1',
        'ready': False,
        'credential_source': 'service_account_file',
        'reason': 'credential_file_unreadable',
        'timeout_seconds': 1.25,
        'max_workers': 2,
    }
    assert '/v1/mobile/push/audit' in summary['endpoints']
    assert '/v1/devices/me/push-token' in summary['endpoints']
    assert '/srv/one' not in json.dumps(summary['push_sender'])


def test_server_cli_reuses_handoff_and_update_rotation_preserves_claimed_device(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_dir = tmp_path / 'mobile-state'
    monkeypatch.setattr('cli.services.mobile.mobile_host_state_dir', lambda: state_dir)
    client = _FakeCcbdClient(project_id='proj-one', project_root='/srv/one', display_name='one')
    registry = MobileGatewayProjectRegistry([
        MobileGatewayProject('proj-one', Path('/srv/one'), lambda: client, display_name='one'),
    ])
    command = SimpleNamespace(listen='127.0.0.1:0', public_url=None, route_provider='lan')
    first = prepare_server_mobile_gateway(command, project_registry=registry, host_id='host-test')
    first_code = str(first.summary['pairing']['pairing_code'])
    thread = threading.Thread(target=first.server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f'http://{first.server.server_address[0]}:{first.server.server_address[1]}'
        tokens = []
        for index in range(4):
            request = Request(
                f'{base}/v1/pairing/claim',
                data=json.dumps({'pairing_code': first_code, 'device_name': f'Phone {index}'}).encode(),
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urlopen(request, timeout=2) as response:
                tokens.append(json.loads(response.read())['device_token'])
    finally:
        first.server.shutdown()
        first.close()
        thread.join(timeout=2)

    restarted = prepare_server_mobile_gateway(command, project_registry=registry, host_id='host-test')
    try:
        assert restarted.summary['pairing']['pairing_code'] == first_code
    finally:
        restarted.close()

    rotated = prepare_server_mobile_gateway(
        command,
        project_registry=registry,
        host_id='host-test',
        rotate_pairing=True,
    )
    assert rotated.summary['pairing']['pairing_code'] != first_code
    thread = threading.Thread(target=rotated.server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f'http://{rotated.server.server_address[0]}:{rotated.server.server_address[1]}'
        denied = Request(
            f'{base}/v1/pairing/claim',
            data=json.dumps({'pairing_code': first_code}).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with pytest.raises(HTTPError) as error:
            urlopen(denied, timeout=2)
        assert error.value.code == 410
        me = Request(f'{base}/v1/devices/me', headers={'Authorization': f'Bearer {tokens[0]}'})
        with urlopen(me, timeout=2) as response:
            assert json.loads(response.read())['status'] == 'ok'
    finally:
        rotated.server.shutdown()
        rotated.close()
        thread.join(timeout=2)


@requires_af_unix
def test_prepare_server_mobile_gateway_uses_published_registry_without_proc(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_dir = tmp_path / 'mobile-state'
    registry_path = state_dir / 'projects.json'
    project_root = tmp_path / 'mac-running-project'
    project_root.mkdir()
    project_id = compute_project_id(project_root)

    class _RegistryCcbdClient:
        def __init__(self, _socket_path: Path) -> None:
            pass

        def ping(self, target: str) -> dict[str, object]:
            return {
                'status': 'ok',
                'project_id': project_id,
                'project_root': str(project_root),
                'display_name': 'mac-running-project',
                'health': 'healthy',
                'mount_state': 'mounted',
            }

    with tempfile.TemporaryDirectory(prefix='ccb-sock-', dir='/tmp') as socket_dir:
        socket_path = Path(socket_dir) / 'ccbd.sock'
        unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        unix_socket.bind(str(socket_path))
        publish_mobile_gateway_project(
            project_id=project_id,
            project_root=project_root,
            ccbd_socket_path=socket_path,
            display_name='mac-running-project',
            registry_path=registry_path,
        )
        monkeypatch.setattr(
            'cli.services.mobile.discover_running_mobile_gateway_projects',
            lambda: (),
        )
        monkeypatch.setattr(
            'mobile_gateway.project_registry.discover_running_mobile_gateway_projects',
            lambda: (),
        )
        monkeypatch.setattr(
            'mobile_gateway.project_registry.mobile_host_state_dir',
            lambda: state_dir,
        )
        monkeypatch.setattr(
            'mobile_gateway.project_registry.CcbdClient',
            _RegistryCcbdClient,
        )
        monkeypatch.setattr(
            'cli.services.mobile.mobile_host_state_dir',
            lambda: state_dir,
        )

        try:
            handle = prepare_server_mobile_gateway(
                SimpleNamespace(
                    listen='127.0.0.1:0',
                    public_url=None,
                    route_provider='lan',
                ),
                host_id='host-test',
            )
            try:
                assert handle.summary['project_count'] == 1
                assert handle.summary['projects'][0]['id'] == project_id
                assert (
                    handle.summary['projects'][0]['display_name']
                    == 'mac-running-project'
                )
            finally:
                handle.close()
        finally:
            unix_socket.close()
            socket_path.unlink(missing_ok=True)


def test_prepare_server_mobile_gateway_fails_without_running_projects(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr('cli.services.mobile.discover_running_mobile_gateway_projects', lambda: ())
    monkeypatch.setattr('cli.services.mobile.mobile_host_state_dir', lambda: tmp_path / 'mobile-state')

    with pytest.raises(ValueError, match='no running CCB projects'):
        prepare_server_mobile_gateway(
            SimpleNamespace(listen='127.0.0.1:0', public_url=None, route_provider='lan'),
            host_id='host-test',
        )


def test_prepare_server_mobile_gateway_uses_host_registry_without_socket_leak(tmp_path: Path, monkeypatch) -> None:
    first = _FakeCcbdClient(project_id='proj-one', project_root='/srv/one', display_name='one')
    second = _FakeCcbdClient(project_id='proj-two', project_root='/srv/two', display_name='two')
    registry = MobileGatewayProjectRegistry(
        [
            MobileGatewayProject(
                project_id='proj-one',
                project_root=Path('/srv/one'),
                ccbd_client_factory=lambda: first,
                display_name='one',
            ),
            MobileGatewayProject(
                project_id='proj-two',
                project_root=Path('/srv/two'),
                ccbd_client_factory=lambda: second,
                display_name='two',
            ),
        ]
    )
    monkeypatch.setattr('cli.services.mobile.mobile_host_state_dir', lambda: tmp_path / 'mobile-state')

    handle = prepare_server_mobile_gateway(
        SimpleNamespace(listen='127.0.0.1:0', public_url=None, route_provider='lan'),
        project_registry=registry,
        host_id='host-test',
    )
    try:
        summary = handle.summary
    finally:
        handle.close()

    assert summary['mode'] == 'loopback_server_registry'
    assert summary['host_id'] == 'host-test'
    assert summary['project_id'] == 'host-test'
    assert summary['project_count'] == 2
    assert [item['id'] for item in summary['projects']] == ['proj-one', 'proj-two']
    assert summary['pairing']['project_id'] == 'host-test'
    assert summary['pairing']['gateway_url'].startswith('http://127.0.0.1:')
    assert 'ccbd.sock' not in json.dumps(summary)
    assert first.calls == []
    assert second.calls == []
