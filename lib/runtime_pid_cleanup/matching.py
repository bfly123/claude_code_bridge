from __future__ import annotations

import os
from pathlib import Path


def pid_matches_project(
    pid: int,
    *,
    project_root: Path,
    hint_paths: tuple[Path, ...],
    read_proc_path_fn,
    read_proc_cmdline_fn,
    path_within_fn,
    os_name: str = os.name,
) -> bool:
    normalized_hints = normalize_hint_roots(project_root, hint_paths=hint_paths)
    if os_name == 'nt':
        return _windows_pid_matches_project(
            pid,
            normalized_hints=normalized_hints,
            hint_paths=hint_paths,
            read_proc_path_fn=read_proc_path_fn,
            read_proc_cmdline_fn=read_proc_cmdline_fn,
            path_within_fn=path_within_fn,
        )
    cwd_path = read_proc_path_fn(pid, 'cwd')
    if cwd_path is not None:
        for root in normalized_hints:
            if path_within_fn(cwd_path, root):
                return True
    cmdline = read_proc_cmdline_fn(pid)
    if cmdline:
        for candidate in (*normalized_hints, *hint_paths):
            text = str(candidate).strip()
            if text and text in cmdline:
                return True
    return False


def normalize_hint_roots(project_root: Path, *, hint_paths: tuple[Path, ...]) -> list[Path]:
    normalized: list[Path] = []
    for candidate in (project_root, *(path.parent for path in hint_paths)):
        try:
            resolved = candidate.expanduser().resolve()
        except Exception:
            resolved = candidate.expanduser().absolute()
        if resolved not in normalized:
            normalized.append(resolved)
    return normalized


def path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except Exception:
        return False
    return True


def _windows_pid_matches_project(
    pid: int,
    *,
    normalized_hints: list[Path],
    hint_paths: tuple[Path, ...],
    read_proc_path_fn,
    read_proc_cmdline_fn,
    path_within_fn,
) -> bool:
    exe_path = read_proc_path_fn(pid, 'exe')
    if exe_path is not None:
        for root in normalized_hints:
            if path_within_fn(exe_path, root):
                return True
    cmdline = str(read_proc_cmdline_fn(pid) or '').strip()
    if not cmdline:
        return False
    for candidate in (*normalized_hints, *hint_paths):
        text = str(candidate).strip()
        if text and text in cmdline:
            return True
    marker = str(project_root_marker(normalized_hints)).strip()
    return bool(marker and marker in cmdline)


def project_root_marker(normalized_hints: list[Path]) -> Path:
    for candidate in normalized_hints:
        if candidate.name == '.ccb':
            return candidate
        ccb_root = candidate / '.ccb'
        return ccb_root
    return Path('.ccb')


__all__ = ['normalize_hint_roots', 'path_within', 'pid_matches_project']
