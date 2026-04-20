from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar('T')


class JsonlStore:
    def append(
        self,
        path: Path,
        row: T | dict[str, Any],
        serializer: Callable[[T], dict[str, Any]] | None = None,
    ) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if serializer is None:
            if not isinstance(row, dict):
                raise ValueError('serializer is required for non-dict rows')
            payload = row
        else:
            payload = serializer(row)
        with target.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + '\n')

    def read_all(self, path: Path, loader: Callable[[dict[str, Any]], T] | None = None) -> list[T] | list[dict[str, Any]]:
        target = Path(path)
        if not target.exists():
            return []
        rows: list[T] | list[dict[str, Any]] = []
        with target.open('r', encoding='utf-8') as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                payload = json.loads(text)
                if not isinstance(payload, dict):
                    raise ValueError(f'{path}: expected JSON object rows')
                rows.append(loader(payload) if loader else payload)
        return rows

    def read_since(
        self,
        path: Path,
        start_line: int = 0,
        loader: Callable[[dict[str, Any]], T] | None = None,
    ) -> tuple[int, list[T] | list[dict[str, Any]]]:
        if start_line < 0:
            raise ValueError('start_line cannot be negative')
        target = Path(path)
        if not target.exists():
            return start_line, []
        rows: list[T] | list[dict[str, Any]] = []
        current = 0
        with target.open('r', encoding='utf-8') as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                current += 1
                if current <= start_line:
                    continue
                payload = json.loads(text)
                if not isinstance(payload, dict):
                    raise ValueError(f'{path}: expected JSON object rows')
                rows.append(loader(payload) if loader else payload)
        return current, rows
