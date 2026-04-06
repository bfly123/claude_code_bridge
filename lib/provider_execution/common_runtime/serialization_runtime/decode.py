from __future__ import annotations

import base64
from pathlib import Path


def deserialize_runtime_state(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [deserialize_runtime_state(item) for item in value]
    if isinstance(value, dict):
        marker = value.get('__ccb_type__')
        return _deserialize_marker(value, marker)
    return value


def _deserialize_marker(value: dict, marker: object) -> object:
    if marker == 'path':
        return Path(str(value.get('value') or '')).expanduser()
    if marker == 'bytes':
        encoded = str(value.get('value') or '')
        return base64.b64decode(encoded.encode('ascii')) if encoded else b''
    if marker == 'tuple':
        return tuple(deserialize_runtime_state(item) for item in value.get('items', []))
    return {str(key): deserialize_runtime_state(item) for key, item in value.items()}


__all__ = ['deserialize_runtime_state']
