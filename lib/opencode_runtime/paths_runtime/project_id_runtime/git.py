from __future__ import annotations

import os
from pathlib import Path


def find_git_dir(start: Path) -> tuple[Path | None, Path | None]:
    for candidate in [start, *start.parents]:
        git_entry = candidate / ".git"
        if not git_entry.exists():
            continue
        resolved = resolve_git_entry(candidate, git_entry)
        if resolved is not None:
            return resolved
    return None, None


def resolve_git_entry(candidate: Path, git_entry: Path) -> tuple[Path, Path] | None:
    if git_entry.is_dir():
        return candidate, git_entry
    if not git_entry.is_file():
        return None
    try:
        raw = git_entry.read_text(encoding="utf-8", errors="replace").strip()
        prefix = "gitdir:"
        if raw.lower().startswith(prefix):
            gitdir = raw[len(prefix) :].strip()
            gitdir_path = Path(gitdir)
            if not gitdir_path.is_absolute():
                gitdir_path = (candidate / gitdir_path).resolve()
            return candidate, gitdir_path
    except Exception:
        return None
    return None


def read_cached_project_id(git_dir: Path | None) -> str | None:
    if not git_dir:
        return None
    try:
        cache_path = git_dir / "opencode"
        if not cache_path.exists():
            return None
        cached = cache_path.read_text(encoding="utf-8", errors="replace").strip()
        return cached or None
    except Exception:
        return None


def git_root_commit_cwd(git_root: Path | None, cwd: Path) -> str:
    return str(git_root or cwd)


def windows_startupinfo():
    import subprocess

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return startupinfo


def apply_windows_process_options(kwargs: dict[str, object]) -> None:
    if os.name == "nt":
        kwargs["startupinfo"] = windows_startupinfo()


__all__ = [
    'apply_windows_process_options',
    'find_git_dir',
    'git_root_commit_cwd',
    'read_cached_project_id',
    'resolve_git_entry',
]
