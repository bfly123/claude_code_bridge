from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import tempfile
from typing import Any, Literal

from agents.models import normalize_agent_name
from ccbd.api_models import TargetKind


TARGET_SEGMENT_PATTERN = re.compile(r'[^a-z0-9._-]+')
UNIX_SOCKET_SAFE_BYTES = 100
_WSL_MOUNTED_DRIVE_RE = re.compile(r'^/mnt/([A-Za-z])(?:/|$)')


@dataclass(frozen=True)
class SocketPlacement:
    preferred_path: Path
    effective_path: Path
    root_kind: Literal['project', 'runtime']
    fallback_reason: str | None = None
    filesystem_hint: str | None = None


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
    candidates = runtime_socket_root_candidates()
    for candidate in candidates:
        if pathname_unix_socket_supported(candidate):
            return candidate
    if candidates:
        return candidates[0]
    return Path('/tmp').expanduser() / 'ccb-runtime'


def runtime_socket_root_candidates() -> tuple[Path, ...]:
    candidates: list[Path] = []
    xdg_runtime_dir = str(os.environ.get('XDG_RUNTIME_DIR') or '').strip()
    if xdg_runtime_dir:
        candidates.append(Path(xdg_runtime_dir).expanduser() / 'ccb-runtime')
    candidates.append(Path('/tmp').expanduser() / 'ccb-runtime')
    candidates.append(Path(tempfile.gettempdir()).expanduser() / 'ccb-runtime')
    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return tuple(unique)


def is_wsl() -> bool:
    if os.environ.get('WSL_INTEROP') or os.environ.get('WSL_DISTRO_NAME'):
        return True
    proc_version = Path('/proc/version')
    try:
        return 'microsoft' in proc_version.read_text(encoding='utf-8', errors='ignore').lower()
    except Exception:
        return False


def socket_filesystem_hint(path: Path) -> str | None:
    normalized = str(Path(path).expanduser()).replace('\\', '/')
    if is_wsl() and _WSL_MOUNTED_DRIVE_RE.match(normalized):
        return 'wsl_drvfs'
    return None


def pathname_unix_socket_supported(path: Path) -> bool:
    return socket_filesystem_hint(path) != 'wsl_drvfs'


def choose_socket_placement(
    *,
    preferred_path: Path,
    project_socket_key: str,
) -> SocketPlacement:
    preferred = Path(preferred_path).expanduser()
    if not unix_socket_path_is_safe(preferred):
        return _runtime_socket_placement(
            preferred_path=preferred,
            project_socket_key=project_socket_key,
            fallback_reason='path_too_long',
            filesystem_hint=socket_filesystem_hint(preferred),
        )
    filesystem_hint = socket_filesystem_hint(preferred)
    if not pathname_unix_socket_supported(preferred):
        return _runtime_socket_placement(
            preferred_path=preferred,
            project_socket_key=project_socket_key,
            fallback_reason='unsupported_filesystem',
            filesystem_hint=filesystem_hint,
        )
    return SocketPlacement(
        preferred_path=preferred,
        effective_path=preferred,
        root_kind='project',
        fallback_reason=None,
        filesystem_hint=filesystem_hint,
    )


def socket_placement_payload(placement: SocketPlacement, *, prefix: str = '') -> dict[str, Any]:
    field_prefix = f'{prefix}_' if prefix else ''
    return {
        f'{field_prefix}preferred_socket_path': str(placement.preferred_path),
        f'{field_prefix}effective_socket_path': str(placement.effective_path),
        f'{field_prefix}socket_root_kind': placement.root_kind,
        f'{field_prefix}socket_fallback_reason': placement.fallback_reason,
        f'{field_prefix}socket_filesystem_hint': placement.filesystem_hint,
    }


def _runtime_socket_placement(
    *,
    preferred_path: Path,
    project_socket_key: str,
    fallback_reason: str,
    filesystem_hint: str | None,
) -> SocketPlacement:
    stem = preferred_path.stem
    effective_root = runtime_socket_root()
    return SocketPlacement(
        preferred_path=preferred_path,
        effective_path=effective_root / f'{stem}-{project_socket_key}.sock',
        root_kind='runtime',
        fallback_reason=fallback_reason,
        filesystem_hint=filesystem_hint,
    )


__all__ = [
    'SocketPlacement',
    'TARGET_SEGMENT_PATTERN',
    'UNIX_SOCKET_SAFE_BYTES',
    'choose_socket_placement',
    'is_wsl',
    'normalized_segment',
    'pathname_unix_socket_supported',
    'runtime_socket_root',
    'runtime_socket_root_candidates',
    'socket_placement_payload',
    'socket_filesystem_hint',
    'target_segment',
    'unix_socket_path_is_safe',
]
