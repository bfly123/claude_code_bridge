from __future__ import annotations

import ctypes
import hashlib
import os
from pathlib import Path

try:
    from ctypes import wintypes
except Exception:  # pragma: no cover
    wintypes = None


_PROCESS_ASSIGN_TO_JOB_ACCESS = 0x0101
_JOB_OBJECT_TERMINATE = 0x0008
_JOB_OBJECT_ASSIGN_PROCESS = 0x0001


def runtime_job_object_name(runtime_dir: Path | str) -> str:
    normalized = str(Path(runtime_dir).expanduser()).replace('/', '\\').casefold()
    digest = hashlib.sha1(normalized.encode('utf-8')).hexdigest()[:24]
    return f'Local\\ccb-{digest}'


def assign_process_to_named_job(job_name: str, pid: int, *, kernel32=None) -> bool:
    if os.name != 'nt':
        return False
    normalized_name = str(job_name or '').strip()
    if not normalized_name:
        return False
    normalized_pid = _normalize_pid(pid)
    if normalized_pid is None:
        return False
    kernel = _kernel32(kernel32)
    job_handle = None
    process_handle = None
    try:
        job_handle = kernel.CreateJobObjectW(None, normalized_name)
        if not job_handle:
            return False
        process_handle = kernel.OpenProcess(_PROCESS_ASSIGN_TO_JOB_ACCESS, False, normalized_pid)
        if not process_handle:
            return False
        return bool(kernel.AssignProcessToJobObject(job_handle, process_handle))
    except Exception:
        return False
    finally:
        _close_handle(kernel, process_handle)
        _close_handle(kernel, job_handle)


def terminate_named_job(job_name: str, *, exit_code: int = 1, kernel32=None) -> bool:
    if os.name != 'nt':
        return False
    normalized_name = str(job_name or '').strip()
    if not normalized_name:
        return False
    kernel = _kernel32(kernel32)
    job_handle = None
    try:
        job_handle = kernel.OpenJobObjectW(_JOB_OBJECT_TERMINATE | _JOB_OBJECT_ASSIGN_PROCESS, False, normalized_name)
        if not job_handle:
            return False
        return bool(kernel.TerminateJobObject(job_handle, int(exit_code)))
    except Exception:
        return False
    finally:
        _close_handle(kernel, job_handle)


def _normalize_pid(value: object) -> int | None:
    text = str(value or '').strip()
    if not text.isdigit():
        return None
    pid = int(text)
    return pid if pid > 0 else None


def _kernel32(kernel32=None):
    if kernel32 is not None:
        return kernel32
    if wintypes is None:
        raise RuntimeError('wintypes unavailable')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenJobObjectW.restype = wintypes.HANDLE
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    return kernel


def _close_handle(kernel, handle) -> None:
    if handle is None:
        return
    try:
        if not handle:
            return
    except Exception:
        return
    try:
        kernel.CloseHandle(handle)
    except Exception:
        return


__all__ = ['assign_process_to_named_job', 'runtime_job_object_name', 'terminate_named_job']
