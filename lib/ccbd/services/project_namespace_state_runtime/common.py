from __future__ import annotations

from ccbd.models import SCHEMA_VERSION

NAMESPACE_STATE_RECORD_TYPE = 'ccbd_project_namespace_state'
NAMESPACE_EVENT_RECORD_TYPE = 'ccbd_project_namespace_event'


def clean_text(value: object) -> str | None:
    text = str(value or '').strip()
    return text or None


def require_schema_version(payload: dict[str, object]) -> None:
    if payload.get('schema_version') != SCHEMA_VERSION:
        raise ValueError(f'schema_version must be {SCHEMA_VERSION}')


def require_record_type(payload: dict[str, object], *, record_type: str) -> None:
    if payload.get('record_type') != record_type:
        raise ValueError(f"record_type must be '{record_type}'")


__all__ = [
    'NAMESPACE_EVENT_RECORD_TYPE',
    'NAMESPACE_STATE_RECORD_TYPE',
    'clean_text',
    'require_record_type',
    'require_schema_version',
]
