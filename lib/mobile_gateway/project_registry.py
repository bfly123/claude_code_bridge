from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Callable

from ccbd.socket_client import CcbdClient
from ccbd.control_plane_transport.endpoint_store import read_endpoint
from storage.atomic import atomic_write_json
from project.ids import normalize_project_path
from project.identity_store import load_project_identity


@dataclass(frozen=True)
class MobileGatewayProject:
    project_id: str
    project_root: Path
    ccbd_client_factory: Callable[[], object]
    display_name: str | None = None

    def __post_init__(self) -> None:
        project_id = str(self.project_id or '').strip()
        if not project_id:
            raise ValueError('project_id cannot be empty')
        object.__setattr__(self, 'project_id', project_id)
        object.__setattr__(self, 'project_root', Path(self.project_root))
        display_name = str(self.display_name or '').strip() or None
        object.__setattr__(self, 'display_name', display_name)

    def client(self):
        return self.ccbd_client_factory()

    @property
    def public_display_name(self) -> str:
        return self.display_name or self.project_root.name or self.project_id


class MobileGatewayProjectRegistry:
    def __init__(self, projects: list[MobileGatewayProject] | tuple[MobileGatewayProject, ...]) -> None:
        ordered: list[MobileGatewayProject] = []
        by_id: dict[str, MobileGatewayProject] = {}
        for project in projects:
            if project.project_id in by_id:
                raise ValueError(f'duplicate mobile gateway project: {project.project_id}')
            ordered.append(project)
            by_id[project.project_id] = project
        if not ordered:
            raise ValueError('mobile gateway project registry cannot be empty')
        self._ordered = tuple(ordered)
        self._by_id = dict(by_id)

    @classmethod
    def current_project(
        cls,
        *,
        project_id: str,
        project_root: Path,
        ccbd_client_factory: Callable[[], object],
    ) -> MobileGatewayProjectRegistry:
        return cls(
            [
                MobileGatewayProject(
                    project_id=project_id,
                    project_root=project_root,
                    ccbd_client_factory=ccbd_client_factory,
                )
            ]
        )

    @property
    def default_project(self) -> MobileGatewayProject:
        return self._ordered[0]

    def projects(self) -> tuple[MobileGatewayProject, ...]:
        return self._ordered

    def get(self, project_id: str) -> MobileGatewayProject | None:
        return self._by_id.get(str(project_id or '').strip())


HOST_PROJECT_REGISTRY_RECORD_TYPE = 'ccb_mobile_host_project_registry'
HOST_PROJECT_REGISTRY_FILENAME = 'projects.json'


def mobile_host_state_dir() -> Path:
    explicit = str(os.environ.get('CCB_MOBILE_HOST_STATE_HOME') or '').strip()
    if explicit:
        return Path(explicit).expanduser()
    xdg_state_home = str(os.environ.get('XDG_STATE_HOME') or '').strip()
    if xdg_state_home:
        return Path(xdg_state_home).expanduser() / 'ccb' / 'mobile'
    return Path.home().expanduser() / '.local' / 'state' / 'ccb' / 'mobile'


def mobile_host_project_registry_path(*, state_dir: Path | None = None) -> Path:
    return Path(state_dir or mobile_host_state_dir()).expanduser() / HOST_PROJECT_REGISTRY_FILENAME


def publish_mobile_gateway_project(
    *,
    project_id: str,
    project_root: Path,
    ccbd_socket_path: Path,
    display_name: str | None = None,
    registry_path: Path | None = None,
    updated_at: str | None = None,
) -> None:
    path = Path(registry_path or mobile_host_project_registry_path()).expanduser()
    payload = _read_registry_payload(path)
    projects = _registry_projects(payload)
    normalized = MobileGatewayProject(
        project_id=project_id,
        project_root=project_root,
        ccbd_client_factory=lambda: None,
        display_name=display_name,
    )
    identity = load_project_identity(normalized.project_root)
    if identity is not None and identity.project_id != normalized.project_id:
        return
    root_key = normalize_project_path(normalized.project_root)
    projects = {
        key: record for key, record in projects.items()
        if normalize_project_path(str(record.get('project_root') or '')) != root_key
    }
    projects[normalized.project_id] = {
        'project_id': normalized.project_id,
        'display_name': normalized.public_display_name,
        'project_root': str(normalized.project_root),
        'ccbd_socket_path': str(Path(ccbd_socket_path).expanduser()),
        **({'updated_at': str(updated_at)} if updated_at else {}),
    }
    atomic_write_json(
        path,
        {
            'schema_version': 1,
            'record_type': HOST_PROJECT_REGISTRY_RECORD_TYPE,
            'projects': [projects[key] for key in sorted(projects)],
        },
    )


def load_mobile_gateway_project_registry(
    *,
    registry_path: Path | None = None,
    include_running: bool = False,
) -> MobileGatewayProjectRegistry:
    path = Path(registry_path or mobile_host_project_registry_path()).expanduser()
    payload = _read_registry_payload(path)
    projects_by_id: dict[str, MobileGatewayProject] = {}
    for record in _registry_projects(payload).values():
        project = _project_from_record(record)
        if project is not None:
            projects_by_id[project.project_id] = project
    if include_running:
        for project in discover_running_mobile_gateway_projects():
            projects_by_id[project.project_id] = project
    return MobileGatewayProjectRegistry(list(projects_by_id.values()))


def discover_running_mobile_gateway_projects(
    *,
    process_root: Path | None = None,
    cmdlines: list[list[str]] | tuple[list[str], ...] | None = None,
) -> tuple[MobileGatewayProject, ...]:
    discovered: dict[str, MobileGatewayProject] = {}
    for argv in cmdlines if cmdlines is not None else _read_proc_cmdlines(process_root or Path('/proc')):
        project_root = _project_root_from_ccbd_cmdline(argv)
        if project_root is None:
            continue
        try:
            project_root = project_root.expanduser().resolve()
            project_id = _compute_project_id(project_root)
            socket_path = _ccbd_socket_path_for_project(project_root)
        except Exception:
            continue
        if not _control_plane_endpoint_is_structurally_valid(socket_path):
            continue
        discovered[project_id] = MobileGatewayProject(
            project_id=project_id,
            project_root=project_root,
            display_name=project_root.name,
            ccbd_client_factory=lambda socket_path=socket_path: CcbdClient(socket_path),
        )
    return tuple(discovered.values())


def _read_registry_payload(path: Path) -> dict[str, object]:
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    if str(data.get('record_type') or '').strip() != HOST_PROJECT_REGISTRY_RECORD_TYPE:
        return {}
    return data


def _registry_projects(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    raw = payload.get('projects')
    records = raw if isinstance(raw, list) else []
    projects: dict[str, dict[str, object]] = {}
    for item in records:
        if not isinstance(item, dict):
            continue
        project_id = str(item.get('project_id') or '').strip()
        if not project_id:
            continue
        projects[project_id] = dict(item)
    return projects


def _project_from_record(record: dict[str, object]) -> MobileGatewayProject | None:
    project_id = str(record.get('project_id') or '').strip()
    root_text = str(record.get('project_root') or '').strip()
    socket_text = str(record.get('ccbd_socket_path') or '').strip()
    if not project_id or not root_text or not socket_text:
        return None
    project_root = Path(root_text).expanduser()
    socket_path = Path(socket_text).expanduser()
    if not project_root.is_absolute() or not socket_path.is_absolute():
        return None
    if not project_root.exists() or not _control_plane_endpoint_is_structurally_valid(socket_path):
        return None
    identity = load_project_identity(project_root)
    if identity is not None and identity.project_id != project_id:
        return None
    display_name = str(record.get('display_name') or '').strip() or None
    return MobileGatewayProject(
        project_id=project_id,
        project_root=project_root,
        display_name=display_name,
        ccbd_client_factory=lambda socket_path=socket_path: CcbdClient(socket_path),
    )


def _read_proc_cmdlines(process_root: Path) -> list[list[str]]:
    cmdlines: list[list[str]] = []
    try:
        entries = list(Path(process_root).iterdir())
    except Exception:
        return cmdlines
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / 'cmdline').read_bytes()
        except Exception:
            continue
        parts = [part.decode('utf-8', errors='replace') for part in raw.split(b'\0') if part]
        if parts:
            cmdlines.append(parts)
    return cmdlines


def _project_root_from_ccbd_cmdline(argv: list[str]) -> Path | None:
    if not _is_ccbd_main_cmdline(argv):
        return None
    for index, token in enumerate(argv):
        if token == '--project' and index + 1 < len(argv):
            value = argv[index + 1]
            return Path(value) if str(value or '').strip() else None
        if token.startswith('--project='):
            value = token.split('=', 1)[1]
            return Path(value) if str(value or '').strip() else None
    return None


def _is_ccbd_main_cmdline(argv: list[str]) -> bool:
    for index, token in enumerate(argv):
        normalized = str(token or '').replace('\\', '/')
        if normalized.endswith('/ccbd/main.py'):
            return True
        if token == '-m' and index + 1 < len(argv) and argv[index + 1] == 'ccbd.main':
            return True
    return False


def _compute_project_id(project_root: Path) -> str:
    from project.ids import compute_project_id

    return compute_project_id(project_root)


def _ccbd_socket_path_for_project(project_root: Path) -> Path:
    from storage.paths import PathLayout

    return PathLayout(project_root).ccbd_socket_path


def _control_plane_endpoint_is_structurally_valid(socket_path: Path) -> bool:
    # Linux, macOS, and WSL use the POSIX Unix-socket transport. Native Windows
    # uses a regular-file marker plus a tcp_loopback descriptor. Keep those
    # representations disjoint because CcbdClient selects transport by host OS.
    if os.name != 'nt':
        return socket_path.is_socket()
    if not socket_path.is_file():
        return False
    try:
        endpoint = read_endpoint(socket_path)
    except (OSError, ValueError):
        return False
    if not isinstance(endpoint, dict):
        return False
    if endpoint.get('kind') != 'tcp_loopback':
        return False
    # token 是 Windows TCP 控制平面认证的必要项，缺失则 CcbdClient 必然连不上。
    if not str(endpoint.get('token_ref') or endpoint.get('auth_ref') or '').strip():
        return False
    # tcp_loopback 仅允许 127.0.0.1（与 WindowsTcpControlPlaneTransport 安全模型一致）。
    host = str(endpoint.get('host') or '').strip() or '127.0.0.1'
    return host == '127.0.0.1'


__all__ = [
    'HOST_PROJECT_REGISTRY_FILENAME',
    'HOST_PROJECT_REGISTRY_RECORD_TYPE',
    'MobileGatewayProject',
    'MobileGatewayProjectRegistry',
    'discover_running_mobile_gateway_projects',
    'load_mobile_gateway_project_registry',
    'mobile_host_project_registry_path',
    'mobile_host_state_dir',
    'publish_mobile_gateway_project',
]
