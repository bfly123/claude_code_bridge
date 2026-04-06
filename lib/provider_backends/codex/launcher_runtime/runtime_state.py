from __future__ import annotations

from pathlib import Path
import os


def prepare_runtime(runtime_dir: Path) -> dict[str, object]:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    input_fifo = runtime_dir / 'input.fifo'
    output_fifo = runtime_dir / 'output.fifo'
    ensure_fifo(input_fifo, 0o600)
    ensure_fifo(output_fifo, 0o644)
    return {
        'input_fifo': input_fifo,
        'output_fifo': output_fifo,
    }


def ensure_fifo(path: Path, mode: int) -> None:
    if path.exists():
        return
    os.mkfifo(path, mode)


__all__ = ['prepare_runtime']
