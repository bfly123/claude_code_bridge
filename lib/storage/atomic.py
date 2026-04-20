from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, text: str, *, encoding: str = 'utf-8') -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.tmp', dir=str(target.parent))
    try:
        with os.fdopen(fd, 'w', encoding=encoding) as handle:
            handle.write(text)
        os.replace(tmp_name, target)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def atomic_write_json(path: Path, payload: Any, *, encoding: str = 'utf-8') -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding=encoding)
