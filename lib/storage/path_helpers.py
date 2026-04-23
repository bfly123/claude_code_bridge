from __future__ import annotations

from pathlib import Path
import os
import re
import tempfile

from agents.models import normalize_agent_name
from ccbd.api_models import TargetKind


TARGET_SEGMENT_PATTERN = re.compile(r'[^a-z0-9._-]+')
UNIX_SOCKET_SAFE_BYTES = 100
_EXPERIMENTAL_TRUE_VALUES = {'1', 'true', 'yes', 'on'}


def normalized_segment(value: str, *, label: str) -> str:
    normalized = TARGET_SEGMENT_PATTERN.sub(
        '-',
        str(value or '').strip().lower(),
    ).strip('-.')
    if not normalized:
        raise ValueError(f'{label} cannot be empty')
    return normalized


def target_segment(target_kind: TargetKind | str, target_name: str) -> str:
    kind = TargetKind(target_kind)
    raw_name = str(target_name or '').strip()
    if kind is TargetKind.AGENT:
        return normalize_agent_name(raw_name)
    return normalized_segment(raw_name, label='target_name')


def unix_socket_path_is_safe(path: Path) -> bool:
    return len(os.fsencode(str(path))) <= UNIX_SOCKET_SAFE_BYTES


def runtime_socket_root() -> Path:
    base = os.environ.get('XDG_RUNTIME_DIR') or tempfile.gettempdir()
    return Path(base).expanduser() / 'ccb-runtime'


def experimental_windows_native_enabled() -> bool:
    raw = str(os.environ.get('CCB_EXPERIMENTAL_WINDOWS_NATIVE') or '').strip().lower()
    return raw in _EXPERIMENTAL_TRUE_VALUES


def default_ipc_kind() -> str:
    raw = str(os.environ.get('CCB_IPC_KIND') or '').strip().lower()
    if raw in {'unix_socket', 'named_pipe'}:
        return raw
    if os.name == 'nt' and experimental_windows_native_enabled():
        return 'named_pipe'
    return 'unix_socket'


def named_pipe_ref(*, project_socket_key: str, stem: str) -> str:
    normalized_stem = normalized_segment(stem, label='stem')
    normalized_key = normalized_segment(project_socket_key, label='project_socket_key')
    return rf'\\.\pipe\ccb-{normalized_key}-{normalized_stem}'


__all__ = [
    'TARGET_SEGMENT_PATTERN',
    'UNIX_SOCKET_SAFE_BYTES',
    'default_ipc_kind',
    'experimental_windows_native_enabled',
    'named_pipe_ref',
    'normalized_segment',
    'runtime_socket_root',
    'target_segment',
    'unix_socket_path_is_safe',
]
