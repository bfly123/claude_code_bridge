from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, TypeVar

from storage.atomic import atomic_write_text

T = TypeVar('T')


class JsonStore:
    def load(self, path: Path, loader: Callable[[dict[str, Any]], T] | None = None) -> T | dict[str, Any]:
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(payload, dict):
            raise ValueError(f'{path}: expected JSON object')
        if loader is None:
            return payload
        return loader(payload)

    def save(
        self,
        path: Path,
        value: T | dict[str, Any],
        serializer: Callable[[T], dict[str, Any]] | None = None,
    ) -> None:
        if serializer is None:
            if not isinstance(value, dict):
                raise ValueError('serializer is required for non-dict values')
            payload = value
        else:
            payload = serializer(value)
        atomic_write_text(Path(path), json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
