from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .utils import coerce_pid


def read_pid_file(path: Path) -> int | None:
    try:
        return coerce_pid(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def read_proc_path(pid: int, entry: str) -> Path | None:
    if os.name == 'nt':
        return _read_windows_process_path(pid, entry)
    try:
        return Path(os.readlink(f'/proc/{pid}/{entry}')).expanduser()
    except Exception:
        return None


def read_proc_cmdline(pid: int) -> str:
    if os.name == 'nt':
        return _read_windows_process_commandline(pid)
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


def _read_windows_process_path(pid: int, entry: str) -> Path | None:
    if entry != 'exe' or pid <= 0:
        return None
    text = _run_windows_process_query(
        pid,
        property_name='ExecutablePath',
    )
    if not text:
        return None
    try:
        return Path(text).expanduser()
    except Exception:
        return None


def _read_windows_process_commandline(pid: int) -> str:
    if pid <= 0:
        return ''
    return _run_windows_process_query(pid, property_name='CommandLine')


def _run_windows_process_query(pid: int, *, property_name: str) -> str:
    command = (
        f"$p = Get-CimInstance Win32_Process -Filter \"ProcessId={int(pid)}\"; "
        f"if ($p) {{ [Console]::Out.Write($p.{property_name}) }}"
    )
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', command],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return ''
    if result.returncode != 0:
        return ''
    return str(result.stdout or '').strip()


__all__ = ['read_pid_file', 'read_proc_cmdline', 'read_proc_path', 'remove_pid_files']
