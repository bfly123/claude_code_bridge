from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents.models import normalize_agent_name
from storage.json_store import JsonStore

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ProviderHelperManifest:
    agent_name: str
    runtime_generation: int
    helper_kind: str
    leader_pid: int
    pgid: int | None
    started_at: str | None
    owner_daemon_generation: int | None
    state: str = 'running'

    def __post_init__(self) -> None:
        object.__setattr__(self, 'agent_name', normalize_agent_name(self.agent_name))
        object.__setattr__(self, 'runtime_generation', max(1, int(self.runtime_generation)))
        object.__setattr__(self, 'leader_pid', int(self.leader_pid))
        object.__setattr__(self, 'pgid', int(self.pgid) if self.pgid is not None else None)
        object.__setattr__(self, 'helper_kind', str(self.helper_kind or '').strip())
        object.__setattr__(self, 'state', str(self.state or '').strip() or 'running')
        if self.leader_pid <= 0:
            raise ValueError('leader_pid must be positive')
        if not self.helper_kind:
            raise ValueError('helper_kind cannot be empty')

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'provider_helper_manifest',
            'agent_name': self.agent_name,
            'runtime_generation': self.runtime_generation,
            'helper_kind': self.helper_kind,
            'leader_pid': self.leader_pid,
            'pgid': self.pgid,
            'started_at': self.started_at,
            'owner_daemon_generation': self.owner_daemon_generation,
            'state': self.state,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'ProviderHelperManifest':
        _validate_record(record, 'provider_helper_manifest')
        return cls(
            agent_name=str(record['agent_name']),
            runtime_generation=int(record['runtime_generation']),
            helper_kind=str(record['helper_kind']),
            leader_pid=int(record['leader_pid']),
            pgid=(int(record['pgid']) if record.get('pgid') is not None else None),
            started_at=str(record.get('started_at') or '').strip() or None,
            owner_daemon_generation=(
                int(record['owner_daemon_generation']) if record.get('owner_daemon_generation') is not None else None
            ),
            state=str(record.get('state') or 'running'),
        )


def load_helper_manifest(path: Path, *, store: JsonStore | None = None) -> ProviderHelperManifest | None:
    if not path.exists():
        return None
    current_store = store or JsonStore()
    return current_store.load(path, loader=ProviderHelperManifest.from_record)


def save_helper_manifest(path: Path, manifest: ProviderHelperManifest, *, store: JsonStore | None = None) -> Path:
    current_store = store or JsonStore()
    current_store.save(path, manifest, serializer=lambda value: value.to_record())
    return path


def clear_helper_manifest(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def sync_runtime_helper_manifest(paths, runtime) -> ProviderHelperManifest | None:
    helper_path = paths.agent_helper_path(runtime.agent_name)
    manifest = build_runtime_helper_manifest(runtime)
    if manifest is None:
        clear_helper_manifest(helper_path)
        return None
    save_helper_manifest(helper_path, manifest)
    return manifest


def build_runtime_helper_manifest(runtime) -> ProviderHelperManifest | None:
    provider = str(getattr(runtime, 'provider', '') or '').strip().lower()
    if provider != 'codex':
        return None
    runtime_root = str(getattr(runtime, 'runtime_root', '') or '').strip()
    if not runtime_root:
        return None
    leader_pid = _read_pid(Path(runtime_root) / 'bridge.pid')
    if leader_pid is None:
        return None
    runtime_generation = _canonical_runtime_generation(runtime)
    if runtime_generation is None:
        return None
    return ProviderHelperManifest(
        agent_name=str(getattr(runtime, 'agent_name')),
        runtime_generation=runtime_generation,
        helper_kind='codex_bridge',
        leader_pid=leader_pid,
        pgid=leader_pid,
        started_at=str(getattr(runtime, 'started_at', '') or getattr(runtime, 'last_seen_at', '') or '').strip() or None,
        owner_daemon_generation=(
            int(getattr(runtime, 'daemon_generation')) if getattr(runtime, 'daemon_generation', None) is not None else None
        ),
        state='running',
    )


def _canonical_runtime_generation(runtime) -> int | None:
    try:
        generation = int(getattr(runtime, 'runtime_generation', None))
    except Exception:
        return None
    return generation if generation > 0 else None


def _read_pid(path: Path) -> int | None:
    try:
        raw = path.read_text(encoding='utf-8').strip()
    except Exception:
        return None
    if not raw.isdigit():
        return None
    pid = int(raw)
    return pid if pid > 0 else None


def _validate_record(record: dict[str, Any], expected_type: str) -> None:
    if record.get('schema_version') != SCHEMA_VERSION:
        raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
    if record.get('record_type') != expected_type:
        raise ValueError(f'record_type must be {expected_type!r}')


__all__ = [
    'ProviderHelperManifest',
    'SCHEMA_VERSION',
    'build_runtime_helper_manifest',
    'clear_helper_manifest',
    'load_helper_manifest',
    'save_helper_manifest',
    'sync_runtime_helper_manifest',
]
