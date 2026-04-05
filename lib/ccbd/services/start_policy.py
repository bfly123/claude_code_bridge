from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ccbd.models import SCHEMA_VERSION
from storage.json_store import JsonStore
from storage.paths import PathLayout

_START_POLICY_RECORD_TYPE = 'ccbd_start_policy'


@dataclass(frozen=True)
class CcbdStartPolicy:
    project_id: str
    auto_permission: bool
    recovery_restore: bool = True
    last_started_at: str | None = None
    source: str = 'start_command'

    def __post_init__(self) -> None:
        if not str(self.project_id or '').strip():
            raise ValueError('project_id cannot be empty')
        if not str(self.source or '').strip():
            raise ValueError('source cannot be empty')

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': _START_POLICY_RECORD_TYPE,
            'project_id': self.project_id,
            'auto_permission': self.auto_permission,
            'recovery_restore': self.recovery_restore,
            'last_started_at': self.last_started_at,
            'source': self.source,
        }

    @classmethod
    def from_record(cls, payload: dict[str, Any]) -> CcbdStartPolicy:
        if payload.get('schema_version') != SCHEMA_VERSION:
            raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
        if payload.get('record_type') != _START_POLICY_RECORD_TYPE:
            raise ValueError(f"record_type must be '{_START_POLICY_RECORD_TYPE}'")
        return cls(
            project_id=str(payload['project_id']),
            auto_permission=bool(payload.get('auto_permission')),
            recovery_restore=bool(payload.get('recovery_restore', True)),
            last_started_at=_clean_text(payload.get('last_started_at')),
            source=str(payload.get('source') or 'start_command'),
        )

    def summary_fields(self) -> dict[str, object]:
        return {
            'start_policy_auto_permission': self.auto_permission,
            'start_policy_recovery_restore': self.recovery_restore,
            'start_policy_last_started_at': self.last_started_at,
            'start_policy_source': self.source,
        }


class CcbdStartPolicyStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self) -> CcbdStartPolicy | None:
        path = self._layout.ccbd_start_policy_path
        if not path.exists():
            return None
        return self._store.load(path, loader=CcbdStartPolicy.from_record)

    def save(self, policy: CcbdStartPolicy) -> None:
        self._store.save(self._layout.ccbd_start_policy_path, policy, serializer=lambda value: value.to_record())

    def clear(self) -> None:
        try:
            self._layout.ccbd_start_policy_path.unlink()
        except FileNotFoundError:
            pass


def recovery_start_options(policy: CcbdStartPolicy | None) -> tuple[bool, bool]:
    if policy is None:
        return False, False
    return bool(policy.recovery_restore), bool(policy.auto_permission)


def _clean_text(value: object) -> str | None:
    text = str(value or '').strip()
    return text or None


__all__ = [
    'CcbdStartPolicy',
    'CcbdStartPolicyStore',
    'recovery_start_options',
]
