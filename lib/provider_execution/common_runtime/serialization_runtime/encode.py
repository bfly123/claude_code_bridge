from __future__ import annotations

import base64
from pathlib import Path


def serialize_runtime_state(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return {'__ccb_type__': 'path', 'value': str(value.expanduser())}
    if isinstance(value, bytes):
        return {'__ccb_type__': 'bytes', 'value': base64.b64encode(value).decode('ascii')}
    if isinstance(value, tuple):
        return {'__ccb_type__': 'tuple', 'items': [serialize_runtime_state(item) for item in value]}
    if isinstance(value, list):
        return [serialize_runtime_state(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialize_runtime_state(item) for key, item in value.items()}
    return str(value)


__all__ = ['serialize_runtime_state']
