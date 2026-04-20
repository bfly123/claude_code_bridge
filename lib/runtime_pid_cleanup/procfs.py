from __future__ import annotations

import os
from pathlib import Path

from .utils import coerce_pid


def read_pid_file(path: Path) -> int | None:
    try:
        return coerce_pid(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def read_proc_path(pid: int, entry: str) -> Path | None:
    try:
        return Path(os.readlink(f'/proc/{pid}/{entry}')).expanduser()
    except Exception:
        return None


def read_proc_cmdline(pid: int) -> str:
    try:
        raw = Path(f'/proc/{pid}/cmdline').read_bytes()
    except Exception:
        return ''
    return raw.replace(b'\x00', b' ').decode('utf-8', errors='ignore').strip()


def remove_pid_files(paths: tuple[Path, ...]) -> None:
    for path in paths:
        if path.suffix != '.pid':
            continue
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        except Exception:
            continue


__all__ = ['read_pid_file', 'read_proc_cmdline', 'read_proc_path', 'remove_pid_files']
